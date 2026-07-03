"""Verificación de última mano contra la ficha de Amazon.

Su ÚNICO trabajo imprescindible es traer las estrellas reales del producto
(el feed no las da). De paso comprueba que la ficha carga (precio vivo / no captcha).

IMPORTANTE: el precio que muestra la ficha NO es fiable para el descuento (Amazon
enseña una variante por defecto que puede no ser la de la oferta). El descuento se
calcula con datos de Slickdeals. Aquí el precio es solo informativo / señal de vida.

AVISO: scrapear Amazon va contra sus ToS y puede empezar a devolver captchas/503
bajo volumen o desde IPs de datacenter. Uso conservador y espaciado. La vía limpia
definitiva es la PA-API (Fase 2, tras las primeras ventas).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from ..sources.base import DEFAULT_HEADERS

_RATING_RE = re.compile(r"([0-9]\.[0-9]|[0-9])\s+out of 5 stars", re.IGNORECASE)
_PRICE_RE = re.compile(r'<span class="a-offscreen">\$([0-9,]+\.[0-9]{2})</span>')
# Imagen de producto en alta resolución (Amazon la incrusta en el JSON de la ficha).
_IMAGE_RE = re.compile(r'"hiRes":"(https://[^"\\]+?\.jpg)"', re.IGNORECASE)
_IMAGE_FALLBACK_RE = re.compile(r'data-old-hires="(https://[^"]+?\.jpg)"', re.IGNORECASE)
_CAPTCHA_RE = re.compile(
    r"robot check|enter the characters|automated access|/errors/validateCaptcha",
    re.IGNORECASE,
)


@dataclass
class VerifyResult:
    ok: bool                      # ¿se pudo leer la ficha?
    rating: Optional[float] = None
    price: Optional[float] = None  # solo informativo (ver nota arriba)
    image: Optional[str] = None    # URL de imagen de producto (hiRes)
    captcha: bool = False
    reason: str = ""              # diagnóstico: ok / captcha / error / sin-rating


class AmazonVerifier:
    def __init__(self, domain: str = "amazon.com", timeout: float = 25.0,
                 delay: float = 1.5) -> None:
        self.domain = domain
        self.delay = delay  # pausa generosa: Amazon es sensible al ritmo
        headers = dict(DEFAULT_HEADERS, **{"Accept-Language": "en-US,en;q=0.9"})
        self._client = httpx.Client(headers=headers, follow_redirects=True, timeout=timeout)

    def verify(self, asin: str, retries: int = 2) -> VerifyResult:
        """Lee la ficha con reintentos y backoff (Amazon es sensible a ráfagas)."""
        url = f"https://www.{self.domain}/dp/{asin}"
        html = ""
        for intento in range(retries + 1):
            try:
                resp = self._client.get(url)
                if resp.status_code == 200:
                    html = resp.text
                    break
                # 503/429/etc: throttling temporal -> esperar más y reintentar
                time.sleep(self.delay * (intento + 2))
            except Exception:
                time.sleep(self.delay * (intento + 2))
        else:
            return VerifyResult(ok=False, reason="error/red")
        time.sleep(self.delay)

        if _CAPTCHA_RE.search(html):
            return VerifyResult(ok=False, captcha=True, reason="captcha")

        rating = self._first_float(_RATING_RE, html)
        price = self._first_float(_PRICE_RE, html, strip_commas=True)
        image = self._image(html)
        if rating is None:
            return VerifyResult(ok=True, price=price, image=image, reason="sin-rating")
        return VerifyResult(ok=True, rating=rating, price=price, image=image, reason="ok")

    @staticmethod
    def _image(html: str) -> Optional[str]:
        m = _IMAGE_RE.search(html) or _IMAGE_FALLBACK_RE.search(html)
        return m.group(1) if m else None

    @staticmethod
    def _first_float(rx: re.Pattern, html: str, strip_commas: bool = False) -> Optional[float]:
        m = rx.search(html)
        if not m:
            return None
        raw = m.group(1).replace(",", "") if strip_commas else m.group(1)
        try:
            return float(raw)
        except ValueError:
            return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AmazonVerifier":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
