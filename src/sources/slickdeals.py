"""Adaptador de Slickdeals (mercado US) a partir de sus feeds RSS.

Slickdeals tiene RSS abierto (sin reto de Cloudflare). De cada ítem nos quedamos
solo si el comercio es Amazon, extraemos el ASIN del enlace de Amazon embebido y
parseamos el/los precio(s) del título. Lo que no venga en el feed (precio anterior
fiable, estrellas) se completará en la 'verificación de última mano'.
"""
from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

import feedparser

from ..conditions import ACCOUNT, detect_condition, extract_code
from ..models import Deal
from .base import ProductDataSource

# ASIN dentro de una URL de Amazon: /dp/XXXXXXXXXX, /gp/product/XXXXXXXXXX...
_ASIN_RE = re.compile(r"/(?:dp|gp/product|gp/aw/d|gp/offer-listing)/([A-Z0-9]{10})",
                      re.IGNORECASE)
# Importes en dólares dentro del título: $5, $9.99, $1,299.00
_PRICE_RE = re.compile(r"\$\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)")


class SlickdealsSource(ProductDataSource):
    name = "slickdeals"

    def __init__(
        self,
        feeds: List[str],
        amazon_domain: str = "amazon.com",
        affiliate_tag: str = "",
        market: str = "us",
        currency: str = "USD",
        **kw,
    ) -> None:
        super().__init__(market=market, **kw)
        self.feeds = feeds
        self.amazon_domain = amazon_domain
        self.affiliate_tag = affiliate_tag
        self.currency = currency

    def fetch(self) -> List[Deal]:
        deals: List[Deal] = []
        for url in self.feeds:
            try:
                raw = self._http_get(url)
            except Exception as exc:  # una fuente caída no debe tumbar el pipeline
                print(f"[slickdeals] aviso: no se pudo leer {url}: {exc}")
                continue
            parsed = feedparser.parse(raw)
            for entry in parsed.entries:
                deal = self._entry_to_deal(entry)
                if deal is not None:
                    deals.append(deal)
        return deals

    # --- internos ------------------------------------------------------------
    def _entry_to_deal(self, entry) -> Optional[Deal]:
        link = (entry.get("link") or "").strip()
        title = (entry.get("title") or "").strip()
        body = self._entry_body(entry)

        # Solo ofertas cuyo comercio sea Amazon.
        if not self._is_amazon(link, body):
            return None

        # Condición del precio. Las de cuenta concreta / YMMV se descartan.
        condition = detect_condition(title, body)
        if condition == ACCOUNT:
            return None
        code = extract_code(title, body)
        if code:
            condition = "code"  # si hay código, la condición es ese código

        asin = self._extract_asin(link, body)
        price_new, price_old = self._extract_prices(title)

        amazon_url = None
        if asin:
            tag = f"?tag={self.affiliate_tag}" if self.affiliate_tag else ""
            amazon_url = f"https://{self.amazon_domain}/dp/{asin}/{tag}"

        return Deal(
            asin=asin,
            title=self._clean_title(title),
            price_new=price_new,
            price_old=price_old,
            currency=self.currency,
            condition=condition,
            code=code,
            source=self.name,
            market=self.market,
            deal_url=link,
            amazon_url=amazon_url,
            published=self._parse_date(entry),
            raw_title=title,
        )

    @staticmethod
    def _entry_body(entry) -> str:
        """Junta description + content:encoded (donde suele estar el link real)."""
        parts = []
        if entry.get("summary"):
            parts.append(entry["summary"])
        for c in entry.get("content", []) or []:
            parts.append(c.get("value", ""))
        return " ".join(parts)

    @staticmethod
    def _is_amazon(link: str, body: str) -> bool:
        text = f"{link} {body}".lower()
        return "amazon." in text or "-at-amazon" in link.lower()

    @staticmethod
    def _extract_asin(link: str, body: str) -> Optional[str]:
        for text in (body, link):
            m = _ASIN_RE.search(text or "")
            if m:
                return m.group(1).upper()
        return None

    @staticmethod
    def _extract_prices(title: str) -> Tuple[Optional[float], Optional[float]]:
        nums = []
        for raw in _PRICE_RE.findall(title):
            try:
                nums.append(float(raw.replace(",", "")))
            except ValueError:
                continue
        if not nums:
            return None, None
        if len(nums) == 1:
            return nums[0], None
        # Heurística inicial: el menor suele ser el precio de oferta; el mayor,
        # el anterior. La verificación de última mano lo confirmará.
        return min(nums), max(nums)

    @staticmethod
    def _clean_title(title: str) -> str:
        """Deja solo el nombre del producto: quita prefijos de condición y precios."""
        t = re.sub(r"^\s*prime members?:?\s*", "", title, flags=re.IGNORECASE)  # "Prime Members: ..."
        t = re.sub(r"^\s*\$[0-9.,]+\s*[|\-–:]\s*", "", t)       # "$0.99 | Producto"
        t = re.split(r"\s+\$[0-9]", t)[0].strip()               # "Producto $9.99 ..."
        return t or title

    @staticmethod
    def _parse_date(entry):
        raw = entry.get("published") or entry.get("updated")
        if not raw:
            return None
        try:
            return parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
