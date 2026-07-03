"""Filtros estáticos: descuento mínimo y rating mínimo.

Orden EFICIENTE pensado para ahorrar recursos caros:
  1. `passes_discount()` usa solo datos ya disponibles (precio oferta del RSS +
     listPrice de Slickdeals) -> GRATIS, sin tocar Amazon.
  2. `passes_rating()` necesita la verificación de Amazon -> solo se llama para las
     ofertas que YA pasaron el descuento.

Los umbrales se leen de config/settings.yaml (sección `filters`).
"""
from __future__ import annotations

from typing import Optional, Tuple

from ..models import Deal


def passes_discount(deal: Deal, min_discount_pct: float) -> Tuple[bool, str]:
    """¿El descuento real llega al mínimo? Usa datos del feed + Slickdeals."""
    pct = deal.discount_pct
    if pct is None:
        return False, "sin precio anterior (no se puede calcular descuento)"
    if pct < min_discount_pct:
        return False, f"descuento {pct}% < {min_discount_pct}%"
    return True, f"descuento {pct}% OK"


def passes_rating(rating: Optional[float], min_rating: float) -> Tuple[bool, str]:
    """¿El rating de Amazon llega al mínimo? (rating viene de la verificación)."""
    if rating is None:
        return False, "sin rating (no verificable)"
    if rating < min_rating:
        return False, f"rating {rating}★ < {min_rating}★"
    return True, f"rating {rating}★ OK"
