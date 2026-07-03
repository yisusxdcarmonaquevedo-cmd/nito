"""Contrato común de toda fuente de ofertas (patrón adaptador).

El pipeline solo conoce esta interfaz: pide `fetch()` y recibe una lista de
`Deal`. No sabe ni le importa si por debajo hay Slickdeals, Reddit u otra cosa.
Añadir una fuente nueva = crear otra subclase de `ProductDataSource`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import httpx

from ..models import Deal

# Cabeceras de navegador real: evitan bloqueos básicos por User-Agent.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class ProductDataSource(ABC):
    """Clase base de la que hereda toda fuente concreta."""

    #: nombre corto de la fuente, p.ej. "slickdeals"
    name: str = "base"

    def __init__(self, market: str = "us", timeout: float = 20.0) -> None:
        self.market = market
        self.timeout = timeout

    @abstractmethod
    def fetch(self) -> List[Deal]:
        """Descarga la fuente y devuelve sus ofertas ya normalizadas."""
        raise NotImplementedError

    # --- utilidad compartida -------------------------------------------------
    def _http_get(self, url: str) -> bytes:
        """GET con cabeceras de navegador siguiendo redirecciones."""
        with httpx.Client(
            headers=DEFAULT_HEADERS, follow_redirects=True, timeout=self.timeout
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.content
