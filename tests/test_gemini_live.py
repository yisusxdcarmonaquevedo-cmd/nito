"""Prueba EN VIVO del cerebro Gemini con 3 ofertas reales controladas.

Incluye una oferta fuera de nicho (comida de perro) para verificar que el filtro
cognitivo la RECHAZA (publicar=false). Gasta 3 llamadas de la cuota diaria.

    python -m tests.test_gemini_live
"""
from __future__ import annotations

from src.ai.gemini import GeminiBrain
from src.models import Deal

OFERTAS = [
    Deal(asin="B0D3J6D5D6", title='128GB 11" Apple iPad Air Tablet: M2, Wi-Fi',
         price_new=487.0, price_old=749.0, rating=4.5,
         category="Tecnología y Gadgets"),
    Deal(asin="B0FJY27QH4", title="2-Pc Women's V-Neck Pajama Lounge Set",
         price_new=10.0, price_old=29.99, rating=4.6, category="Moda y Accesorios"),
    Deal(asin="B003P9XG22", title="16-oz Blue Buffalo Health Bars Dog Biscuits",
         price_new=9.2, price_old=27.96, rating=4.8, category=None),  # fuera de nicho
]


def main() -> None:
    brain = GeminiBrain()
    for deal in OFERTAS:
        print("=" * 70)
        print(f"OFERTA: {deal.title}  (-{deal.discount_pct}%, {deal.rating}*)")
        res = brain.process(deal)
        if res is None:
            print("  [sin respuesta / error]")
            continue
        publicar = res.get("publicar")
        print(f"  PUBLICAR : {publicar}   ({res.get('motivo')})")
        print(f"  CATEGORÍA: {res.get('categoria')}")
        if publicar:
            print(f"  TÍTULO   : {res.get('titulo')}")
            print(f"  POST     :\n    " + str(res.get("post")).replace("\n", "\n    "))
    brain.close()


if __name__ == "__main__":
    main()
