"""Genera el fichero que consume la web: web/deals_<market>.json.

Es ACUMULATIVO: cada ejecución añade las nuevas ofertas publicadas al feed
existente, deduplica por ASIN, ordena por fecha (lo nuevo arriba), caduca lo
viejo y limita el total. La web estática solo tiene que leer este JSON.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from ..models import Deal

ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = ROOT / "web"

MAX_AGE_DAYS = 2      # respaldo por tiempo: una oferta desaparece a los 2 días
MAX_DEALS = 120       # tope de ofertas vivas en la web


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_dict(d: Deal) -> dict:
    return {
        "asin": d.asin,
        "title": d.title,
        "title_es": d.title_es,
        "headline": d.headline,
        "post": d.post,
        "post_en": d.post_en,
        "price_new": d.price_new,
        "price_old": d.price_old,
        "currency": d.currency,
        "discount_pct": d.discount_pct,
        "rating": d.rating,
        "category": d.category,
        "image": d.image,
        "url": d.amazon_url,
        "source": d.source,
        "deal_key": d.deal_key,       # para revalidar (sd:<id> -> slickdeals.net/f/<id>)
        "published_at": _now_iso(),
    }


def write_deals(deals: List[Deal], market: str, web_dir: Path = WEB_DIR) -> int:
    """Fusiona las ofertas nuevas con el feed existente y lo reescribe.

    Devuelve el número total de ofertas vivas en el fichero.
    """
    web_dir.mkdir(parents=True, exist_ok=True)
    path = web_dir / f"deals_{market}.json"

    por_asin = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for item in json.load(fh).get("deals", []):
                    por_asin[item.get("asin")] = item
        except (json.JSONDecodeError, OSError):
            por_asin = {}

    for d in deals:
        if d.asin:
            por_asin[d.asin] = _to_dict(d)

    # Caducar lo viejo y ordenar (lo más reciente primero).
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    vivos = [it for it in por_asin.values() if _fresh(it, cutoff)]
    vivos.sort(key=lambda it: it.get("published_at", ""), reverse=True)
    vivos = vivos[:MAX_DEALS]

    salida = {
        "generated_at": _now_iso(),
        "market": market,
        "count": len(vivos),
        "deals": vivos,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, ensure_ascii=False, indent=2)
    return len(vivos)


def _fresh(item: dict, cutoff: datetime) -> bool:
    raw = item.get("published_at")
    if not raw:
        return True
    try:
        return datetime.fromisoformat(raw) >= cutoff
    except ValueError:
        return True
