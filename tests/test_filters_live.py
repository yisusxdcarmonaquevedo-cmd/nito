"""Prueba EN VIVO del Bloque 3: descuento (gratis) + rating (Amazon).

Embudo:  radar -> enriquecer (ASIN + listPrice) -> FILTRO descuento -> verificar
rating en Amazon -> FILTRO rating -> supervivientes finales.

    python -m tests.test_filters_live
"""
from __future__ import annotations

from src.config import build_sources, load_settings
from src.enrich.asin_resolver import AsinResolver
from src.filters.static_filters import passes_discount, passes_rating
from src.verify.amazon import AmazonVerifier

MAX_ENRICH = 12       # páginas de Slickdeals a abrir (cortesía)
MAX_AMAZON = 6        # fichas de Amazon a verificar (muy conservador)


def main() -> None:
    settings = load_settings()
    f = settings["filters"]
    min_disc, min_rating = f["min_discount_pct"], f["min_rating"]

    # 1) Radar + dedupe rápido por URL
    deals = []
    for s in build_sources("us"):
        deals.extend(s.fetch())
    seen, unique = set(), []
    for d in deals:
        if d.deal_url and d.deal_url not in seen:
            seen.add(d.deal_url)
            unique.append(d)
    print(f"Radar: {len(deals)} ofertas ({len(unique)} únicas)\n")

    # 2) Enriquecer (ASIN + listPrice) en una sola descarga por oferta
    resolver = AsinResolver(delay=0.5)
    enriched = []
    for d in unique[:MAX_ENRICH]:
        resolver.enrich(d)
        enriched.append(d)
    resolver.close()

    # 3) FILTRO descuento (gratis, sin tocar Amazon)
    con_descuento = []
    print("--- Filtro 1: DESCUENTO >= {}% ---".format(min_disc))
    for d in enriched:
        ok, motivo = passes_discount(d, min_disc)
        marca = "PASA " if ok else "  -  "
        print(f"  {marca} {str(d.discount_pct or '?'):>5}%  {d.title[:46]:46}  ({motivo})")
        if ok:
            con_descuento.append(d)

    # 4) Verificar rating en Amazon SOLO a los supervivientes del descuento
    print(f"\n--- Filtro 2: RATING >= {min_rating}* (verificando en Amazon) ---")
    verifier = AmazonVerifier(delay=1.5)
    finales = []
    for d in con_descuento[:MAX_AMAZON]:
        res = verifier.verify(d.asin) if d.asin else None
        rating = res.rating if res and res.ok else None
        ok, motivo = passes_rating(rating, min_rating)
        estado = "captcha/err" if (res and not res.ok) else motivo
        marca = "PUBLICA" if ok else "descarta"
        print(f"  {marca}  {d.asin}  {str(rating or '?'):>4}*  {d.title[:40]:40} ({estado})")
        if ok:
            finales.append(d)
    verifier.close()

    print(f"\n=== RESULTADO: {len(finales)} ofertas listas para Gemini ===")
    for d in finales:
        print(f"  -{d.discount_pct}%  {d.price_new}->{d.price_old}  {d.asin}  {d.title[:50]}")


if __name__ == "__main__":
    main()
