"""Sonda de diagnóstico: ¿por qué falla la resolución de ASIN en algunas ofertas?

Para cada oferta de Amazon del feed, descarga su página y reporta:
  - estado HTTP / tamaño
  - si contiene /dp/ASIN
  - una pista del comercio (amazon vs otros)
"""
from __future__ import annotations

import re
import time

import httpx

from src.config import build_sources
from src.sources.base import DEFAULT_HEADERS

_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", re.IGNORECASE)


def main() -> None:
    deals = []
    for s in build_sources("us"):
        deals.extend(s.fetch())

    # quitar duplicados por URL y limitar a 10
    seen, unique = set(), []
    for d in deals:
        if d.deal_url and d.deal_url not in seen:
            seen.add(d.deal_url)
            unique.append(d)
    unique = unique[:10]

    client = httpx.Client(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=25.0)
    for i, d in enumerate(unique, 1):
        try:
            r = client.get(d.deal_url)
            html = r.text
            status = r.status_code
        except Exception as exc:
            print(f"{i:2}. ERROR {exc}")
            continue
        asins = [m.upper() for m in _ASIN_RE.findall(html)]
        has_dp = "SI" if asins else "NO"
        merchant = "amazon" if "amazon." in html.lower() else "otro"
        print(f"{i:2}. HTTP {status} | {len(html):>7} bytes | dp:{has_dp} "
              f"| nº_asin={len(asins)} | {merchant} | {d.title[:42]}")
        if asins:
            from collections import Counter
            top = Counter(asins).most_common(3)
            print(f"      top ASIN: {top}")
        time.sleep(0.7)
    client.close()


if __name__ == "__main__":
    main()
