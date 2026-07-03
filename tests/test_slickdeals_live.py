"""Prueba EN VIVO del adaptador de Slickdeals contra el feed real.

Ejecutar desde la raíz del proyecto:
    python -m tests.test_slickdeals_live

Descarga los feeds del mercado 'us', extrae las ofertas de Amazon y muestra un
resumen + estadísticas de extracción (cuántas con ASIN, precio, % descuento).
No requiere ninguna clave ni cuenta.
"""
from __future__ import annotations

from src.config import build_sources


def main() -> None:
    sources = build_sources("us")
    print(f"Fuentes construidas para 'us': {[s.name for s in sources]}\n")

    all_deals = []
    for source in sources:
        deals = source.fetch()
        print(f"  {source.name}: {len(deals)} ofertas de Amazon")
        all_deals.extend(deals)

    total = len(all_deals)
    print(f"\nTOTAL ofertas de Amazon detectadas: {total}")
    if total == 0:
        print("No se encontraron ofertas de Amazon en este momento.")
        return

    con_asin = sum(1 for d in all_deals if d.asin)
    con_precio = sum(1 for d in all_deals if d.price_new)
    con_descuento = sum(1 for d in all_deals if d.discount_pct is not None)
    print(f"  con ASIN extraído : {con_asin}/{total}")
    print(f"  con precio        : {con_precio}/{total}")
    print(f"  con % descuento   : {con_descuento}/{total}")

    print("\n--- Muestra (primeras 12) ---")
    for d in all_deals[:12]:
        print(" •", d)
        if d.amazon_url:
            print("     ->", d.amazon_url)


if __name__ == "__main__":
    main()
