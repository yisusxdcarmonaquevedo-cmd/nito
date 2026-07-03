"""Punto de entrada del Cazador de Chollos (lo invoca el cron cada 15 min).

Uso:
    python main.py            # mercado por defecto: us
    python main.py es         # otro mercado
"""
from __future__ import annotations

import sys

from src.pipeline import run


def main() -> None:
    market = sys.argv[1] if len(sys.argv) > 1 else "us"
    listas = run(market, verbose=True)
    print(f"\n{len(listas)} ofertas listas para el cerebro (Gemini) en el mercado '{market}'.")


if __name__ == "__main__":
    main()
