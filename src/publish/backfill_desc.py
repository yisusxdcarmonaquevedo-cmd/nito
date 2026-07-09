"""Auto-relleno de descripciones para ofertas publicadas SIN texto.

Cuando la cuota de Gemini se agota, las ofertas de nicho se publican en "modo
degradado" (sin descripción). Este paso usa el presupuesto SOBRANTE de Gemini de
cada ciclo para ir rellenándolas (con batching), de modo que el feed se cura solo.

Prioridad: las ofertas NUEVAS ya se procesan antes (paso 7 del pipeline); esto
solo usa lo que sobre, con un tope pequeño por ciclo para no acaparar la cuota.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from ..ai.gemini import GeminiBrain, QuotaExhausted
from ..db.database import DealStore
from ..models import Deal
from .json_writer import WEB_DIR

HEAL_CALLS_PER_RUN = 3   # llamadas máx./ciclo para curar (deja cuota para lo nuevo)


def backfill_descriptions(market: str, store: DealStore, settings: dict,
                          web_dir: Path = WEB_DIR) -> Tuple[int, int]:
    """Rellena descripciones que falten en deals_<market>.json.

    Devuelve (ofertas_sin_descripcion, rellenadas_ahora).
    """
    g = settings.get("gemini", {})
    daily_limit = g.get("daily_limit", 18)
    batch = g.get("batch_size", 8)
    sobrante = daily_limit - store.gemini_calls_today()
    if sobrante <= 0:
        return (0, 0)

    path = web_dir / f"deals_{market}.json"
    if not path.exists():
        return (0, 0)
    data = json.loads(path.read_text(encoding="utf-8"))
    faltan = [it for it in data.get("deals", []) if not it.get("post")]
    if not faltan:
        return (0, 0)

    presupuesto = min(sobrante, HEAL_CALLS_PER_RUN)
    objetivo = faltan[: presupuesto * batch]

    try:
        brain = GeminiBrain(rpm=g.get("rpm", 5))
    except Exception:
        return (len(faltan), 0)

    llamadas = rellenadas = 0
    try:
        for i in range(0, len(objetivo), batch):
            lote = objetivo[i: i + batch]
            deals = [
                Deal(asin=it.get("asin"), title=it.get("title") or "",
                     price_new=it.get("price_new"), price_old=it.get("price_old"),
                     rating=it.get("rating"), category=it.get("category"))
                for it in lote
            ]
            res = brain.describe_batch(deals)  # solo redacta: sin decisión de publicar
            llamadas += 1
            if not res:
                continue
            por_num = {r.get("i"): r for r in res if isinstance(r, dict)}
            for n, it in enumerate(lote, start=1):
                r = por_num.get(n)
                if r and r.get("post_es"):
                    it["post"] = r["post_es"]
                    it["post_en"] = r.get("post_en")
                    if r.get("titulo_es"):
                        it["title_es"] = r["titulo_es"]
                    rellenadas += 1
    except QuotaExhausted:
        pass
    finally:
        brain.close()
        store.add_gemini_calls(llamadas)

    if rellenadas:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return (len(faltan), rellenadas)
