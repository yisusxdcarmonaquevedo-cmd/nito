"""Prueba EN VIVO de la revalidación + backfill del deal_key en el feed real.

Parte A: comprueba que _is_expired detecta bien una oferta VIVA (espera False).
Parte B: rellena el deal_key que les falta a las ofertas ya publicadas (desde la
         BD), para que la revalidación pueda comprobarlas en la próxima pasada.

    python -m tests.test_revalidate_live
"""
from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from pathlib import Path

import httpx

from src.publish.json_writer import WEB_DIR
from src.revalidate.checker import _is_expired, revalidate_feed
from src.sources.base import DEFAULT_HEADERS

ROOT = Path(__file__).resolve().parent.parent


def parte_a() -> None:
    print("=== Parte A: detectar oferta VIVA ===")
    c = httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=20.0)
    xml = c.get("https://slickdeals.net/newsearch.php?mode=frontpage&searchin=first&rss=1").text
    live_id = re.search(r"slickdeals\.net/f/(\d+)", xml).group(1)
    html = c.get(f"https://slickdeals.net/f/{live_id}").text
    c.close()
    print(f"  id vivo {live_id} -> _is_expired = {_is_expired(html, live_id)} (espera False)")

    web = Path(tempfile.mkdtemp())
    (web / "deals_us.json").write_text(
        json.dumps({"deals": [{"asin": "LIVE", "deal_key": f"sd:{live_id}", "title": "t"}]}),
        encoding="utf-8",
    )
    print(f"  revalidate_feed -> {revalidate_feed('us', web_dir=web)} (espera (1, 0, 1))")


def parte_b() -> None:
    print("\n=== Parte B: backfill deal_key en el feed real ===")
    feed = WEB_DIR / "deals_us.json"
    db = ROOT / "data" / "chollos.db"
    if not feed.exists() or not db.exists():
        print("  (falta feed o BD, se omite)")
        return
    con = sqlite3.connect(db)
    mapa = {a: k for a, k in con.execute("SELECT asin, deal_key FROM deals WHERE asin IS NOT NULL")}
    con.close()
    data = json.loads(feed.read_text(encoding="utf-8"))
    n = 0
    for d in data.get("deals", []):
        if not d.get("deal_key") and d.get("asin") in mapa:
            d["deal_key"] = mapa[d["asin"]]
            n += 1
    feed.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  deal_key rellenados: {n}")


if __name__ == "__main__":
    parte_a()
    parte_b()
