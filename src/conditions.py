"""Detección de la CONDICIÓN de un chollo de Slickdeals.

El precio anunciado por Slickdeals suele requerir algo para lograrse (ser Prime,
recortar un cupón, meter un código, Suscríbete y Ahorra) o ser específico de
cuentas concretas. Detectarlo permite:
  (a) DESCARTAR las de cuenta concreta / YMMV (imposibles de representar bien), y
  (b) ETIQUETAR el resto, para que el precio mostrado sea honesto ("con cupón"...).
"""
from __future__ import annotations

import re

# Precio para cuentas concretas o inconsistente -> DESCARTAR (no representable).
_ACCOUNT = re.compile(r"select\s+(amazon\s+)?acc|\bYMMV\b|targeted", re.IGNORECASE)
# Requiere un código promocional al pagar.
_CODE = re.compile(r"promo\s*code|coupon\s*code|w/\s*code\b|\bcode:\s*\w", re.IGNORECASE)
# Requiere recortar un cupón en la ficha.
_COUPON = re.compile(r"\bcoupon\b|after\s+clip", re.IGNORECASE)
# Precio exclusivo para miembros Prime.
_PRIME = re.compile(r"prime\s+members?|prime\s+exclusive|w/\s*prime|prime\s+day", re.IGNORECASE)
# Requiere Suscríbete y Ahorra.
_SNS = re.compile(r"subscribe\s*&?\s*save|\bS&S\b|\bSNS\b", re.IGNORECASE)

ACCOUNT = "account"


def detect_condition(*texts: str):
    """Devuelve 'account' (descartar), 'coupon', 'code', 'prime', 'sns' o None."""
    t = " ".join(x for x in texts if x)
    if _ACCOUNT.search(t):
        return ACCOUNT
    if _CODE.search(t):
        return "code"
    if _COUPON.search(t):
        return "coupon"
    if _PRIME.search(t):
        return "prime"
    if _SNS.search(t):
        return "sns"
    return None
