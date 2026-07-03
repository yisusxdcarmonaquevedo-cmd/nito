"""Clasificación barata por palabras clave (config/categories.yaml).

Primer intento SIN gastar cuota de IA: si el título contiene una keyword de una
categoría, la asignamos. Lo que quede sin clasificar lo afinará Gemini (que ya
vamos a llamar de todos modos).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CATS_PATH = ROOT / "config" / "categories.yaml"


@lru_cache(maxsize=1)
def _categorias() -> dict:
    with open(CATS_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("categorias", {})


def classify(title: str) -> Optional[str]:
    """Devuelve el nombre de la categoría, o None si no encaja ninguna keyword."""
    t = (title or "").lower()
    for _key, cfg in _categorias().items():
        for kw in cfg.get("keywords", []):
            if kw.lower() in t:
                return cfg.get("nombre")
    return None


def category_names() -> list:
    """Lista de los nombres de las 6 categorías (para el prompt de Gemini)."""
    return [cfg.get("nombre") for cfg in _categorias().values() if cfg.get("nombre")]
