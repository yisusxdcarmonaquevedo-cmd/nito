"""Revalidación del feed: elimina las ofertas caducadas de deals_<market>.json.

Señal usada (validada en vivo): la página de Slickdeals incluye, junto al
`threadId` de la oferta PRINCIPAL, el campo `"isExpiredDeal":"Yes"|"No"`. Es la
forma fiable de saber si ESA oferta murió (no confunde con las relacionadas), y
Slickdeals no nos bloquea (a diferencia de Amazon).

Para no recargar, cada ciclo se revisa solo un lote (las de comprobación más
antigua), rotando; el respaldo por tiempo (MAX_AGE_DAYS) cubre el resto.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import httpx

from ..publish.json_writer import WEB_DIR
from ..sources.base import DEFAULT_HEADERS

MAX_REVALIDATE_PER_RUN = 15   # ofertas a re-comprobar por ejecución (rota entre ciclos)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _deal_id(deal_key: Optional[str]) -> Optional[str]:
    if deal_key and deal_key.startswith("sd:"):
        return deal_key[3:]
    return None


def _is_expired(html: str, deal_id: str) -> Optional[bool]:
    """True=caducada, False=viva, None=no se pudo determinar (se conserva)."""
    m = re.search(
        r'"isExpiredDeal":"(Yes|No)"\s*,\s*"threadId":' + re.escape(deal_id), html
    )
    if not m:
        return None
    return m.group(1) == "Yes"


def revalidate_feed(market: str = "us", web_dir: Path = WEB_DIR) -> Tuple[int, int, int]:
    """Re-comprueba un lote del feed y quita las caducadas. Reescribe el JSON.

    Devuelve (comprobadas, caducadas, vivas_restantes).
    """
    path = web_dir / f"deals_{market}.json"
    if not path.exists():
        return (0, 0, 0)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    deals = data.get("deals", [])
    if not deals:
        return (0, 0, 0)

    # Priorizar las de comprobación más antigua (o nunca comprobadas).
    orden = sorted(deals, key=lambda d: d.get("revalidated_at") or "")
    lote = orden[:MAX_REVALIDATE_PER_RUN]

    client = httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=20.0)
    now = _now_iso()
    caducadas, comprobadas = set(), 0
    for d in lote:
        did = _deal_id(d.get("deal_key"))
        if not did:
            continue
        try:
            html = client.get(f"https://slickdeals.net/f/{did}").text
        except Exception:
            time.sleep(0.5)
            continue
        time.sleep(0.5)
        estado = _is_expired(html, did)
        comprobadas += 1
        if estado is True:
            caducadas.add(d.get("asin"))
        else:
            d["revalidated_at"] = now  # viva (o desconocida): marcar y rotar al final
    client.close()

    vivas = [d for d in deals if d.get("asin") not in caducadas]
    data["deals"] = vivas
    data["count"] = len(vivas)
    data["generated_at"] = now
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return (comprobadas, len(caducadas), len(vivas))
