"""Regenera las descripciones del feed con el estilo nuevo (descriptivo + ES/EN).

Usa el modo LOTE: ~8 ofertas por llamada (16 ofertas = 2 llamadas de cuota).
    python -m tests.regen_posts
"""
from __future__ import annotations

import json

from src.ai.gemini import GeminiBrain, QuotaExhausted
from src.db.database import DealStore
from src.models import Deal
from src.publish.json_writer import WEB_DIR

BATCH = 8


def main() -> None:
    path = WEB_DIR / "deals_us.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("deals", [])
    print(f"Ofertas a regenerar: {len(items)} (~{-(-len(items) // BATCH)} llamadas)")

    brain = GeminiBrain()
    store = DealStore()
    llamadas = actualizadas = 0
    try:
        for i in range(0, len(items), BATCH):
            lote = items[i: i + BATCH]
            deals = [
                Deal(asin=it.get("asin"), title=it.get("title") or "",
                     price_new=it.get("price_new"), price_old=it.get("price_old"),
                     rating=it.get("rating"), category=it.get("category"))
                for it in lote
            ]
            res = brain.process_batch(deals)
            llamadas += 1
            if not res:
                print(f"  lote {i // BATCH + 1}: sin respuesta")
                continue
            por_num = {r.get("i"): r for r in res if isinstance(r, dict)}
            for n, it in enumerate(lote, start=1):
                r = por_num.get(n)
                if r and r.get("post_es"):
                    it["post"] = r["post_es"]
                    it["post_en"] = r.get("post_en")
                    if r.get("titulo_es"):
                        it["title_es"] = r["titulo_es"]
                    actualizadas += 1
    except QuotaExhausted:
        print("  cuota agotada: se guarda lo conseguido hasta aquí.")
    finally:
        brain.close()
        store.add_gemini_calls(llamadas)
        print(f"Llamadas Gemini hoy: {store.gemini_calls_today()}")
        store.close()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Descripciones actualizadas: {actualizadas}/{len(items)}")


if __name__ == "__main__":
    main()
