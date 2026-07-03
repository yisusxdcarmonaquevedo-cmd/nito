"""Orquestador del pipeline: encadena Radar -> filtros -> Gemini -> posts.

Una sola función `run(market)` ejecuta de principio a fin los Bloques 1-4. Es lo
que invoca el cron cada 15 minutos (vía main.py).

Embudo:
  1. Radar (fuentes RSS)            -> ofertas brutas
  2. Dedupe por deal_key (SQLite)   -> descarta ya PROCESADAS (con decisión final)
  3. Enriquecer (ASIN + listPrice)  -> 1 fetch/oferta a Slickdeals
  4. Filtro descuento (gratis)      -> >= min_discount_pct
  5. Clasificar categoría (keywords)
  6. Verificar rating en Amazon     -> con caché + reintentos (eslabón frágil)
  7. Cerebro Gemini                 -> coherencia + redacción (respeta cuota diaria)
  8. Persistir decisiones

Regla clave de robustez: solo se marca una oferta como "vista" (y por tanto no se
reprocesa) cuando tiene una DECISIÓN DEFINITIVA. Las que fallan en Amazon por un
error transitorio NO se marcan -> se reintentan en el siguiente ciclo.
"""
from __future__ import annotations

from typing import List, Set

from .ai.gemini import GeminiBrain, QuotaExhausted
from .classify.categories import classify
from .config import build_sources, load_settings
from .db.database import DealStore, deal_key_from_url
from .enrich.asin_resolver import AsinResolver
from .filters.static_filters import passes_discount, passes_rating
from .models import Deal
from .publish.backfill import backfill_ratings
from .publish.backfill_desc import backfill_descriptions
from .publish.json_writer import write_deals
from .revalidate.checker import revalidate_feed
from .verify.amazon import AmazonVerifier

# Topes por ejecución (cortesía con las webs + control de recursos).
MAX_ENRICH_PER_RUN = 25   # páginas de Slickdeals a abrir
MAX_AMAZON_PER_RUN = 10   # ofertas a verificar/pasar por ciclo


def run(market: str = "us", verbose: bool = True) -> List[Deal]:
    settings = load_settings()
    market_cfg = settings["markets"][market]
    f = settings["filters"]
    min_disc, min_rating = f["min_discount_pct"], f["min_rating"]

    store = DealStore()
    terminal: Set[str] = set()  # deal_keys con decisión definitiva

    # 1) Radar -------------------------------------------------------------
    raw: List[Deal] = []
    for source in build_sources(market):
        raw.extend(source.fetch())

    # 2) Dedupe por deal_key (en esta pasada y contra la BD) ----------------
    seen_run, candidates = set(), []
    for d in raw:
        key = deal_key_from_url(d.deal_url) or d.asin or d.title
        if key in seen_run:
            continue
        seen_run.add(key)
        if store.seen_before(key):
            continue  # ya la procesamos definitivamente en un ciclo anterior
        d.deal_key = key
        candidates.append(d)

    # 3) Enriquecer (ASIN + precio de lista) -------------------------------
    enriquecidas = candidates[:MAX_ENRICH_PER_RUN]
    resolver = AsinResolver(delay=0.5)
    for d in enriquecidas:
        resolver.enrich(d)
    resolver.close()

    # 4) Filtro de descuento (gratis) --------------------------------------
    con_descuento = []
    for d in enriquecidas:
        if passes_discount(d, min_disc)[0]:
            con_descuento.append(d)
        else:
            terminal.add(d.deal_key)  # rechazo definitivo por descuento

    # 5) Clasificar categoría (barato) -------------------------------------
    for d in con_descuento:
        d.category = classify(d.title)

    # 6) Verificar rating en Amazon (caché + reintentos) -------------------
    # Con `community_fallback` (bootstrap hasta PA-API): si Amazon no responde,
    # la oferta pasa igualmente — la portada de Slickdeals ya está curada por la
    # comunidad. Se muestra sin estrellas y con la imagen de Slickdeals (og:image).
    fallback = f.get("community_fallback", False)
    verifier = AmazonVerifier(domain=market_cfg["amazon_domain"], delay=2.5)
    listas: List[Deal] = []
    diag = {"sin_asin": 0, "cache": 0, "ok": 0, "fallback": 0, "rating_bajo": 0}
    for d in con_descuento[:MAX_AMAZON_PER_RUN]:
        if not d.asin:
            diag["sin_asin"] += 1
            terminal.add(d.deal_key)  # sin ASIN: no recuperable -> descartar
            continue
        if store.asin_published_today(d.asin, market):
            terminal.add(d.deal_key)
            continue
        rating = store.get_rating(d.asin)  # ¿ya lo consultamos antes?
        if rating is not None:
            diag["cache"] += 1
            d.image = store.get_image(d.asin) or d.image
        else:
            res = verifier.verify(d.asin)
            if res.ok and res.rating is not None:
                rating = res.rating
                store.set_rating(d.asin, rating, res.image)
                diag["ok"] += 1
                d.image = res.image or d.image
            elif fallback:
                # Amazon caído/bloqueado: confiar en la curación de Slickdeals.
                diag["fallback"] += 1
                d.amazon_url = _affiliate_url(market_cfg, d.asin)
                listas.append(d)  # rating=None; imagen = la de Slickdeals
                continue
            else:
                continue  # fallo transitorio: NO marcar -> reintentar otro ciclo
        d.rating = rating
        if passes_rating(rating, min_rating)[0]:
            d.amazon_url = _affiliate_url(market_cfg, d.asin)
            listas.append(d)
        else:
            diag["rating_bajo"] += 1
            terminal.add(d.deal_key)  # rating insuficiente: rechazo definitivo
    verifier.close()

    # 7) Cerebro Gemini (coherencia + redacción), respetando cuota diaria ---
    publicados = _procesar_gemini(listas, settings, store, market, terminal)

    # 8) Persistir decisiones ----------------------------------------------
    for d in candidates:
        if d.deal_key in terminal:
            store.record_seen(d, d.deal_key)
    for d in publicados:
        store.mark_published(d.asin, market)

    # 9) Publicar en la web (deals_<market>.json, acumulativo) -------------
    if publicados:
        total = write_deals(publicados, market)
        print(f"[web] {len(publicados)} nuevas -> deals_{market}.json ({total} ofertas vivas)")

    # 10) Revalidar el feed: quitar las que hayan caducado -----------------
    comprobadas, caducadas, vivas = revalidate_feed(market)
    if comprobadas:
        print(f"[revalida] comprobadas {comprobadas}, caducadas {caducadas}, vivas {vivas}")

    # 11) Rellenar estrellas que falten (ofertas publicadas en degradado) --
    sin_rating, rellenadas = backfill_ratings(market, store, market_cfg["amazon_domain"])
    if sin_rating:
        print(f"[estrellas] sin rating: {sin_rating}, rellenadas ahora: {rellenadas}")

    # 12) Rellenar descripciones que falten con la cuota Gemini sobrante ----
    sin_desc, desc_ok = backfill_descriptions(market, store, settings)
    if sin_desc:
        print(f"[descripciones] sin texto: {sin_desc}, rellenadas ahora: {desc_ok}")

    if verbose:
        print(f"[verify] {diag}")
        _resumen(raw, candidates, con_descuento, listas, publicados, market)
    store.close()
    return publicados


def _procesar_gemini(listas: List[Deal], settings: dict, store: DealStore,
                     market: str, terminal: Set[str]) -> List[Deal]:
    """Envía las mejores ofertas a Gemini sin pasarse del presupuesto diario.

    Si la cuota diaria está agotada (límite gratis real: ~20/día), entra el MODO
    DEGRADADO: se publican sin descripción las ofertas ya clasificadas en nicho
    por keywords. Las descripciones se rellenan otro día (tests/regen_posts.py).
    """
    if not listas:
        return []
    g = settings.get("gemini", {})
    daily_limit = g.get("daily_limit", 18)
    presupuesto = max(0, min(daily_limit - store.gemini_calls_today(),
                             g.get("max_per_run", 6)))

    # Priorizar: primero las clasificadas (de nicho), luego mayor descuento*rating.
    ordenadas = sorted(
        listas,
        key=lambda d: (0 if d.category else 1, -((d.discount_pct or 0) * (d.rating or 4))),
    )

    quota_out = presupuesto == 0
    brain = None
    if not quota_out:
        try:
            brain = GeminiBrain(rpm=g.get("rpm", 5))
        except Exception as exc:
            print(f"[gemini] no disponible: {exc}")
            return []

    publicados, llamadas, degradadas = [], 0, 0
    batch_size = g.get("batch_size", 8)
    idx = 0
    while idx < len(ordenadas):
        lote = ordenadas[idx: idx + batch_size]

        if quota_out or llamadas >= presupuesto:
            # Modo degradado: solo ofertas ya clasificadas en nicho, sin descripción.
            quota_out = True
            for d in lote:
                if d.category:
                    terminal.add(d.deal_key)
                    publicados.append(d)
                    degradadas += 1
            idx += batch_size
            continue

        try:
            resultados = brain.process_batch(lote)
            llamadas += 1
        except QuotaExhausted:
            quota_out = True
            print("[gemini] cuota diaria agotada (429): paso a modo degradado.")
            continue  # el mismo lote se reprocesa en degradado

        if resultados is None:  # error no-cuota: no quemar más cuota con este lote
            for d in lote:
                terminal.add(d.deal_key)
            idx += batch_size
            continue

        por_num = {r.get("i"): r for r in resultados if isinstance(r, dict)}
        for n, d in enumerate(lote, start=1):
            terminal.add(d.deal_key)  # Gemini decidió (sí o no): definitivo
            res = por_num.get(n)
            if res and res.get("publicar"):
                d.category = res.get("categoria") or d.category
                d.title_es = res.get("titulo_es")
                d.post = res.get("post_es") or res.get("post")
                d.post_en = res.get("post_en")
                publicados.append(d)
        idx += batch_size

    if brain:
        brain.close()
    store.add_gemini_calls(llamadas)
    extra = f" (+{degradadas} en modo degradado)" if degradadas else ""
    print(f"[gemini] llamadas hoy: {store.gemini_calls_today()}/{daily_limit}{extra}")
    return publicados


def _affiliate_url(market_cfg: dict, asin: str) -> str:
    tag = market_cfg.get("affiliate_tag", "")
    sufijo = f"?tag={tag}" if tag else ""
    return f"https://{market_cfg['amazon_domain']}/dp/{asin}/{sufijo}"


def _resumen(raw, candidates, con_descuento, listas, publicados, market) -> None:
    print(f"\n===== PIPELINE [{market}] =====")
    print(f"  Radar (brutas)         : {len(raw)}")
    print(f"  Nuevas (tras dedupe)   : {len(candidates)}")
    print(f"  Pasan descuento        : {len(con_descuento)}")
    print(f"  Pasan rating (a Gemini): {len(listas)}")
    print(f"  PUBLICADAS (Gemini OK) : {len(publicados)}")
    print("\n  --- Posts generados ---")
    for d in publicados:
        print(f"  [{d.category}] {d.headline}   (-{d.discount_pct}%, {d.rating}*)")
        print(f"    {d.post}")
        print(f"    -> {d.amazon_url}\n")
