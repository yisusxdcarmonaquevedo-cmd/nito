"""Base de datos SQLite local: registro de ofertas y filtro anti-duplicados.

Dos niveles de deduplicación:
  1. Por `deal_key` (id de la oferta en la fuente): evita volver a procesar/descargar
     una oferta que ya vimos en un ciclo anterior. Ahorra fetches.
  2. Por ASIN + mercado + día: evita publicar dos veces el mismo producto el mismo día.

SQLite viene incluido con Python: cero instalación, cero servidor, coste $0.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from ..models import Deal

# data/chollos.db en la raíz del proyecto.
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = ROOT / "data" / "chollos.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deals (
    deal_key       TEXT PRIMARY KEY,   -- id único de la oferta en la fuente
    asin           TEXT,               -- ASIN de Amazon (puede tardar en resolverse)
    title          TEXT,
    source         TEXT,
    market         TEXT,
    first_seen     TEXT,               -- ISO datetime (primera vez que la vimos)
    last_seen      TEXT,               -- ISO datetime (última vez)
    published_date TEXT                -- YYYY-MM-DD si se publicó, o NULL
);
CREATE INDEX IF NOT EXISTS idx_deals_asin ON deals(asin);

CREATE TABLE IF NOT EXISTS usage (
    day          TEXT PRIMARY KEY,   -- YYYY-MM-DD
    gemini_calls INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ratings (
    asin    TEXT PRIMARY KEY,        -- caché de rating + imagen de Amazon (evita re-consultar)
    rating  REAL,
    image   TEXT,
    checked TEXT
);
"""


def deal_key_from_url(url: Optional[str]) -> Optional[str]:
    """Extrae un id estable de la oferta a partir de su URL de Slickdeals.

    `https://slickdeals.net/f/19703496-...` -> "sd:19703496"
    """
    if not url:
        return None
    m = re.search(r"/f/(\d+)", url)
    return f"sd:{m.group(1)}" if m else url.split("?")[0]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DealStore:
    def __init__(self, path: Path = DEFAULT_DB) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # --- deduplicación nivel 1: ¿ya procesamos esta oferta? ------------------
    def seen_before(self, deal_key: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM deals WHERE deal_key = ?", (deal_key,))
        return cur.fetchone() is not None

    # --- deduplicación nivel 2: ¿este ASIN ya se publicó hoy? ----------------
    def asin_published_today(self, asin: str, market: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM deals WHERE asin = ? AND market = ? AND published_date = ?",
            (asin, market, date.today().isoformat()),
        )
        return cur.fetchone() is not None

    # --- escritura -----------------------------------------------------------
    def record_seen(self, deal: Deal, deal_key: str) -> None:
        """Inserta la oferta (o actualiza last_seen/asin si ya existía)."""
        now = _now()
        if self.seen_before(deal_key):
            self.conn.execute(
                "UPDATE deals SET last_seen = ?, asin = COALESCE(asin, ?) WHERE deal_key = ?",
                (now, deal.asin, deal_key),
            )
        else:
            self.conn.execute(
                "INSERT INTO deals(deal_key, asin, title, source, market, "
                "first_seen, last_seen, published_date) VALUES (?,?,?,?,?,?,?,NULL)",
                (deal_key, deal.asin, deal.title, deal.source, deal.market, now, now),
            )
        self.conn.commit()

    def mark_published(self, asin: str, market: str) -> None:
        self.conn.execute(
            "UPDATE deals SET published_date = ? WHERE asin = ? AND market = ?",
            (date.today().isoformat(), asin, market),
        )
        self.conn.commit()

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]

    # --- presupuesto diario de Gemini ---------------------------------------
    def gemini_calls_today(self) -> int:
        row = self.conn.execute(
            "SELECT gemini_calls FROM usage WHERE day = ?", (date.today().isoformat(),)
        ).fetchone()
        return row[0] if row else 0

    def add_gemini_calls(self, n: int) -> None:
        if n <= 0:
            return
        today = date.today().isoformat()
        self.conn.execute(
            "INSERT INTO usage(day, gemini_calls) VALUES (?, ?) "
            "ON CONFLICT(day) DO UPDATE SET gemini_calls = gemini_calls + ?",
            (today, n, n),
        )
        self.conn.commit()

    # --- caché de ratings + imagen de Amazon --------------------------------
    def get_rating(self, asin: str):
        row = self.conn.execute(
            "SELECT rating FROM ratings WHERE asin = ?", (asin,)
        ).fetchone()
        return row[0] if row else None

    def get_image(self, asin: str):
        row = self.conn.execute(
            "SELECT image FROM ratings WHERE asin = ?", (asin,)
        ).fetchone()
        return row[0] if row else None

    def set_rating(self, asin: str, rating: float, image: str = None) -> None:
        self.conn.execute(
            "INSERT INTO ratings(asin, rating, image, checked) VALUES (?,?,?,?) "
            "ON CONFLICT(asin) DO UPDATE SET rating = ?, image = COALESCE(?, image), checked = ?",
            (asin, rating, image, _now(), rating, image, _now()),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
