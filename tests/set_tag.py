"""Cambia el Tracking ID de Amazon Associates en TODO el sistema de una vez.

Uso (cuando tengas tu tag real):
    python -m tests.set_tag minito-20

Actualiza: config/settings.yaml (para las ofertas futuras) y web/deals_us.json
(los enlaces de las ofertas ya publicadas).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        print("Uso: python -m tests.set_tag <tu-tracking-id>   (ej: minito-20)")
        sys.exit(1)
    tag = sys.argv[1].strip()

    # 1) settings.yaml: affiliate_tag del mercado us
    settings = ROOT / "config" / "settings.yaml"
    texto = settings.read_text(encoding="utf-8")
    texto_nuevo, n1 = re.subn(
        r'(amazon_domain: "amazon\.com"\s*\n\s*affiliate_tag: ")[^"]*(")',
        rf"\g<1>{tag}\g<2>", texto, count=1,
    )
    settings.write_text(texto_nuevo, encoding="utf-8")

    # 2) deals_us.json: reescribir el tag de los enlaces ya publicados
    feed = ROOT / "web" / "deals_us.json"
    n2 = 0
    if feed.exists():
        data = json.loads(feed.read_text(encoding="utf-8"))
        for d in data.get("deals", []):
            url = d.get("url") or ""
            if "?tag=" in url:
                d["url"] = url.split("?tag=")[0] + f"?tag={tag}"
                n2 += 1
        feed.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Tag '{tag}' aplicado: settings.yaml ({n1} cambio), feed ({n2} enlaces).")
    print("Recuerda hacer commit y push para que llegue a la web.")


if __name__ == "__main__":
    main()
