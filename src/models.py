"""Modelo de datos normalizado de una oferta, común a todas las fuentes.

El resto del pipeline trabaja SIEMPRE con objetos `Deal`, sin saber de qué
fuente vienen. Eso es lo que nos permite añadir fuentes/mercados sin tocar la
lógica central.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Deal:
    """Una oferta normalizada, independiente de su origen."""

    # --- Identidad del producto ---
    asin: Optional[str]                 # código ASIN de Amazon (None si no se extrajo)
    title: str                          # título limpio del producto (inglés, de la fuente)
    title_es: Optional[str] = None      # título traducido al español (Gemini)

    # --- Precios ---
    price_new: Optional[float] = None   # precio de la oferta
    price_old: Optional[float] = None   # precio anterior/referencia (si se conoce)
    currency: str = "USD"

    # --- Calidad (se rellena en la verificación de última mano) ---
    rating: Optional[float] = None      # estrellas de Amazon (0-5)

    # --- Clasificación / origen ---
    category: Optional[str] = None      # categoría de la web (se asigna después)
    source: str = "unknown"             # "slickdeals", "reddit"...
    market: str = "us"                  # "us", "es"...
    deal_key: Optional[str] = None      # id único de la oferta en la fuente (dedupe)

    # --- Enlaces / media ---
    deal_url: Optional[str] = None      # página de la oferta en la fuente
    amazon_url: Optional[str] = None    # URL de Amazon ya con tag de afiliado
    image: Optional[str] = None         # URL de la imagen de producto (Amazon hiRes)

    # --- Contenido generado por Gemini (Bloque 4) ---
    headline: Optional[str] = None      # titular llamativo (ya no se muestra en la web)
    post: Optional[str] = None          # descripción en español
    post_en: Optional[str] = None       # descripción en inglés (web bilingüe)

    # --- Metadatos ---
    published: Optional[datetime] = None
    raw_title: str = ""                 # título original sin tocar (para depurar)

    @property
    def discount_pct(self) -> Optional[float]:
        """Descuento real en %, o None si faltan datos para calcularlo."""
        if self.price_old and self.price_new and self.price_old > 0:
            return round((1 - self.price_new / self.price_old) * 100, 1)
        return None

    def __str__(self) -> str:
        desc = f"-{self.discount_pct}%" if self.discount_pct is not None else "—"
        precio = f"{self.price_new}{self.currency}" if self.price_new else "¿precio?"
        antes = f" (antes {self.price_old})" if self.price_old else ""
        return f"[{self.asin or '??????????'}] {precio}{antes} {desc}  {self.title[:55]}"
