"""Prueba EN VIVO del Bloque 2: resolución de ASIN + deduplicación con SQLite.

Ejecutar desde la raíz del proyecto (dos veces para ver el dedupe en acción):
    python -m tests.test_enrich_dedupe_live

1ª ejecución: las ofertas son nuevas -> se resuelve su ASIN y se guardan.
2ª ejecución: ya están en la BD -> se reconocen como conocidas (0 descargas).
"""
from __future__ import annotations

from src.config import build_sources
from src.db.database import DealStore, deal_key_from_url
from src.enrich.asin_resolver import AsinResolver

MAX_RESOLVES = 20  # tope de páginas a descargar por ejecución (cortesía + rapidez)


def main() -> None:
    sources = build_sources("us")
    deals = []
    for s in sources:
        deals.extend(s.fetch())
    print(f"Ofertas del radar: {len(deals)}")

    store = DealStore()
    resolver = AsinResolver(delay=0.5)
    print(f"Ofertas ya en la BD antes de empezar: {store.count()}\n")

    nuevas = conocidas = resueltas = 0
    for deal in deals:
        key = deal_key_from_url(deal.deal_url) or (deal.asin or deal.title)
        if store.seen_before(key):
            conocidas += 1
            continue
        # Oferta nueva: resolver ASIN si falta (con tope de descargas).
        if not deal.asin and resueltas < MAX_RESOLVES:
            deal.asin = resolver.resolve(deal)
            if deal.asin:
                resueltas += 1
        store.record_seen(deal, key)
        nuevas += 1

    resolver.close()

    print(f"  nuevas             : {nuevas}")
    print(f"  ya conocidas       : {conocidas}")
    print(f"  ASIN resueltos web : {resueltas} (tope {MAX_RESOLVES})")
    con_asin = sum(1 for d in deals if d.asin)
    print(f"  ofertas con ASIN   : {con_asin}/{len(deals)}")
    print(f"  total en la BD     : {store.count()}")

    print("\n--- Ofertas con ASIN (muestra) ---")
    shown = 0
    for d in deals:
        if d.asin and shown < 12:
            print(f"  {d.asin}  {d.title[:58]}")
            shown += 1
    store.close()


if __name__ == "__main__":
    main()
