"""Carga de configuración y fábrica de fuentes a partir de config/settings.yaml.

La gracia: el pipeline pide `build_sources("us")` y recibe la lista de fuentes
ya construidas según el YAML. Cambiar de mercado o de fuentes = editar el YAML.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from .sources.base import ProductDataSource
from .sources.slickdeals import SlickdealsSource

# Raíz del proyecto = carpeta padre de src/
ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "config" / "settings.yaml"

# Registro de tipos de fuente -> clase. Añadir una fuente = una línea aquí.
SOURCE_REGISTRY = {
    "slickdeals": SlickdealsSource,
    # "reddit": RedditSource,   # Fase 2
}


def load_settings(path: Path = SETTINGS_PATH) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_sources(market: str, settings: Dict[str, Any] = None) -> List[ProductDataSource]:
    """Crea los objetos de fuente de un mercado a partir de la configuración."""
    settings = settings or load_settings()
    market_cfg = settings["markets"][market]
    sources: List[ProductDataSource] = []

    for src in market_cfg.get("sources", []):
        cls = SOURCE_REGISTRY.get(src["type"])
        if cls is None:
            print(f"[config] aviso: tipo de fuente aún no implementado: '{src['type']}'")
            continue
        sources.append(
            cls(
                feeds=src["feeds"],
                amazon_domain=market_cfg["amazon_domain"],
                affiliate_tag=market_cfg.get("affiliate_tag", ""),
                market=market,
                currency=market_cfg.get("currency", "USD"),
            )
        )
    return sources
