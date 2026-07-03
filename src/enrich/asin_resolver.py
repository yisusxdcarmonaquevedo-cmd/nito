"""Resolución del ASIN de una oferta cuando el feed RSS no lo trae.

La prueba en vivo demostró que solo ~1 de cada 24 ítems del RSS de Slickdeals
incluye el ASIN. Pero su PÁGINA de oferta (`slickdeals.net/f/...`) sí lo contiene
(`/dp/XXXXXXXXXX`). Aquí descargamos esa página y extraemos el ASIN.

Optimización clave: si la oferta YA trae ASIN del feed, no descargamos nada.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Optional

import httpx

from ..models import Deal
from ..sources.base import DEFAULT_HEADERS

# El ASIN aparece en la página de Slickdeals de varias formas. La más fiable y
# frecuente es el atributo `data-aps-asin="XXXXXXXXXX"` (etiqueta de afiliado de
# Amazon); como respaldo, `data-asin` o la URL `/dp/XXXXXXXXXX`.
_ASIN_RE = re.compile(
    r'(?:data-aps-asin="|data-asin="|/(?:dp|gp/product|gp/aw/d)/)([A-Z0-9]{10})',
    re.IGNORECASE,
)

# Precio de lista (PVP) embebido en el JSON de la página: "listPrice":"749.00"
_LISTPRICE_RE = re.compile(r'"listPrice"\s*:\s*"?([0-9]+(?:\.[0-9]{1,2})?)"?', re.IGNORECASE)

# Imagen de producto de la propia página de Slickdeals (respaldo si Amazon falla).
_OGIMAGE_RE = re.compile(r'<meta property="og:image" content="(https://[^"]+)"', re.IGNORECASE)


class AsinResolver:
    """Descarga la página de la oferta y extrae su ASIN (con cortesía/rate-limit)."""

    def __init__(self, timeout: float = 25.0, delay: float = 0.5) -> None:
        self.timeout = timeout
        self.delay = delay  # pausa entre descargas para no martillear la web
        self._client = httpx.Client(
            headers=DEFAULT_HEADERS, follow_redirects=True, timeout=timeout
        )

    def resolve(self, deal: Deal) -> Optional[str]:
        """Devuelve el ASIN de la oferta, descargando su página solo si hace falta."""
        if deal.asin:
            return deal.asin  # ya lo traía el feed: cero descargas
        if not deal.deal_url:
            return None
        html = self._fetch(deal.deal_url)
        return self._pick_asin(html) if html else None

    def enrich(self, deal: Deal) -> None:
        """Rellena en UNA sola descarga el ASIN y el precio de lista (PVP).

        El precio de oferta ya viene del título RSS (deal.price_new); aquí
        añadimos el `listPrice` de Slickdeals para poder calcular el descuento.
        """
        if (deal.asin and deal.price_old and deal.image) or not deal.deal_url:
            return
        html = self._fetch(deal.deal_url)
        if not html:
            return
        if not deal.asin:
            deal.asin = self._pick_asin(html)
        if not deal.price_old:
            deal.price_old = self._pick_list_price(html, deal.price_new)
        if not deal.image:
            m = _OGIMAGE_RE.search(html)
            deal.image = m.group(1) if m else None

    def _fetch(self, url: str) -> Optional[str]:
        try:
            return self._client.get(url).text
        except Exception as exc:  # una página caída no debe tumbar el pipeline
            print(f"[enrich] aviso: no se pudo abrir {url}: {exc}")
            return None
        finally:
            time.sleep(self.delay)

    @staticmethod
    def _pick_asin(html: str) -> Optional[str]:
        """Elige el ASIN principal: el que más se repite en la página.

        La variante principal del producto suele aparecer varias veces; los
        productos 'relacionados' aparecen una sola vez. Heurística a endurecer
        más adelante si hiciera falta.
        """
        matches = [m.upper() for m in _ASIN_RE.findall(html)]
        if not matches:
            return None
        return Counter(matches).most_common(1)[0][0]

    @staticmethod
    def _pick_list_price(html: str, price_new: Optional[float]) -> Optional[float]:
        """Precio de lista (PVP) de la oferta principal.

        La página lista varias ofertas; cogemos el primer `listPrice` que sea
        mayor que el precio de oferta (un PVP válido siempre es superior).
        """
        cands = []
        for raw in _LISTPRICE_RE.findall(html):
            try:
                cands.append(float(raw))
            except ValueError:
                continue
        if not cands:
            return None
        if price_new:
            for c in cands:
                if c > price_new:
                    return c
        return cands[0]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AsinResolver":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
