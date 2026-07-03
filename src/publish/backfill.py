"""Relleno de estrellas (y mejora de imagen) para ofertas ya publicadas.

Las ofertas publicadas en "modo degradado" (Amazon caído) salen sin rating.
Este paso repasa el feed en cada ciclo y reintenta conseguir las estrellas:
  1. Gratis: mira la caché de ratings en SQLite (quizá otro ciclo ya lo logró).
  2. Si no: consulta la ficha de Amazon (pocas por ciclo, con pausa).
Si además consigue la imagen de Amazon (mejor que la de Slickdeals), la actualiza.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from ..db.database import DealStore
from ..verify.amazon import AmazonVerifier
from .json_writer import WEB_DIR

MAX_BACKFILL_PER_RUN = 4   # consultas a Amazon por ciclo (las de caché son gratis)


def backfill_ratings(market: str, store: DealStore, domain: str,
                     web_dir: Path = WEB_DIR) -> Tuple[int, int]:
    """Completa ratings que faltan en deals_<market>.json.

    Devuelve (ofertas_sin_rating_antes, rellenadas_ahora).
    """
    path = web_dir / f"deals_{market}.json"
    if not path.exists():
        return (0, 0)
    data = json.loads(path.read_text(encoding="utf-8"))
    faltan = [it for it in data.get("deals", []) if it.get("rating") is None and it.get("asin")]
    if not faltan:
        return (0, 0)

    verifier = AmazonVerifier(domain=domain, delay=2.5)
    consultas = rellenadas = 0
    for it in faltan:
        asin = it["asin"]
        rating = store.get_rating(asin)          # 1) caché: gratis
        image = store.get_image(asin)
        if rating is None and consultas < MAX_BACKFILL_PER_RUN:
            res = verifier.verify(asin)          # 2) Amazon (limitado)
            consultas += 1
            if res.ok and res.rating is not None:
                rating, image = res.rating, res.image or image
                store.set_rating(asin, rating, res.image)
        if rating is not None:
            it["rating"] = rating
            rellenadas += 1
            # La imagen de Amazon (hiRes) es mejor que la miniatura de Slickdeals.
            if image and "media-amazon" in image:
                it["image"] = image
    verifier.close()

    if rellenadas:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return (len(faltan), rellenadas)
