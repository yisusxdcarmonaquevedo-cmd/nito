"""Cerebro del sistema: Gemini 2.5 Flash (filtro cognitivo + redacción).

Modos:
  - process(deal): una oferta por llamada (usos puntuales).
  - process_batch(deals): ~8 ofertas por llamada. Con el límite gratis real
    (20 peticiones/día por proyecto), es el modo principal: 18 x 8 = ~144/día.

Claves API:
  - GEMINI_API_KEY: una clave.
  - GEMINI_API_KEYS: varias separadas por comas (opcional). Si una devuelve 429
    (cuota agotada), se rota a la siguiente automáticamente. Solo se lanza
    QuotaExhausted cuando TODAS están agotadas.

Devuelve JSON estructurado (responseMimeType=application/json).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

from ..classify.categories import category_names
from ..models import Deal

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / "config" / ".env")

_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class QuotaExhausted(RuntimeError):
    """Cuota diaria del plan gratuito agotada en TODAS las claves (HTTP 429)."""


_INSTRUCCIONES = """Eres el redactor de una web de ofertas de Amazon (Nito) con público \
hispanohablante y angloparlante.

Te doy una oferta detectada automáticamente. Debes:
1) Decidir si MERECE publicarse: solo si es una oferta atractiva, coherente y encaja en una de \
estas categorías: {categorias}. Rechaza (publicar=false) productos fuera de nicho (comida de \
mascotas, comestibles, contenido digital suelto), ofertas incoherentes o poco atractivas.
2) Asignarle la categoría exacta de esa lista.
3) Si se publica, escribir una descripción CORTA (2 frases) DESCRIPTIVA y útil del producto: \
qué es, sus características clave y para quién es. Tono informativo y cercano, NADA de \
sensacionalismo: sin mayúsculas gritonas, sin "¡corre!" ni urgencia artificial, máximo un emoji \
discreto. No inventes datos ni menciones el precio (ya se muestra aparte). Escríbela en español \
y también en inglés.
4) Traducir el título del producto al español de forma natural y corta (mantén las marcas y \
modelos tal cual).

Responde ÚNICAMENTE con este JSON:
{{"publicar": true/false, "motivo": "breve", "categoria": "una de la lista o null", \
"titulo_es": "título traducido o null", \
"post_es": "descripción en español o null", "post_en": "descripción en inglés o null"}}"""

_INSTRUCCIONES_LOTE = """Eres el redactor de una web de ofertas de Amazon (Nito) con público \
hispanohablante y angloparlante.

Te doy {n} ofertas numeradas detectadas automáticamente. Para CADA oferta debes:
1) Decidir si MERECE publicarse: solo si es atractiva, coherente y encaja en una de estas \
categorías: {categorias}. Rechaza (publicar=false) productos fuera de nicho (comida de mascotas, \
comestibles, contenido digital suelto), ofertas incoherentes o poco atractivas.
2) Asignarle la categoría exacta de esa lista.
3) Si se publica, escribir una descripción CORTA (2 frases) DESCRIPTIVA y útil del producto: \
qué es, sus características clave y para quién es. Tono informativo y cercano, NADA de \
sensacionalismo: sin mayúsculas gritonas, sin "¡corre!" ni urgencia artificial, máximo un emoji \
discreto. No inventes datos ni menciones el precio. Escríbela en español y también en inglés.
4) Traducir el título del producto al español de forma natural y corta (mantén las marcas y \
modelos tal cual).

Responde ÚNICAMENTE con un array JSON de {n} objetos, uno por oferta y en el mismo orden:
[{{"i": 1, "publicar": true/false, "categoria": "una de la lista o null", \
"titulo_es": "título traducido o null", "post_es": "... o null", "post_en": "... o null"}}, ...]"""


class GeminiBrain:
    def __init__(self, model: Optional[str] = None, rpm: int = 5, timeout: float = 60.0) -> None:
        raw = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY") or ""
        self.keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not self.keys:
            raise RuntimeError("Falta GEMINI_API_KEY (o GEMINI_API_KEYS) en config/.env")
        self._key_idx = 0
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.rpm = rpm
        self._calls: list[float] = []  # timestamps para el limitador RPM
        self._client = httpx.Client(timeout=timeout)

    # --- limitador de ritmo (RPM) --------------------------------------------
    def _throttle(self) -> None:
        now = time.time()
        self._calls = [t for t in self._calls if now - t < 60]
        if len(self._calls) >= self.rpm:
            espera = 60 - (now - self._calls[0]) + 0.5
            if espera > 0:
                print(f"[gemini] límite RPM: esperando {espera:.1f}s...")
                time.sleep(espera)
        self._calls.append(time.time())

    # --- petición con rotación de claves --------------------------------------
    def _generate(self, prompt: str, temperature: float) -> Optional[dict]:
        """POST a la API. Rota de clave si la actual da 429. None si error normal."""
        self._throttle()
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "temperature": temperature},
        }
        while True:
            url = _API_URL.format(model=self.model) + f"?key={self.keys[self._key_idx]}"
            try:
                resp = self._client.post(url, json=body)
            except Exception as exc:
                print(f"[gemini] error de red: {exc}")
                return None
            if resp.status_code == 429:
                if self._key_idx + 1 < len(self.keys):
                    self._key_idx += 1
                    print(f"[gemini] clave agotada; rotando a la clave #{self._key_idx + 1}...")
                    continue
                raise QuotaExhausted("cuota diaria agotada en todas las claves")
            try:
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                print(f"[gemini] error en la llamada: {exc}")
                return None

    # --- una oferta ------------------------------------------------------------
    def process(self, deal: Deal) -> Optional[dict]:
        data = self._generate(self._prompt(deal), temperature=0.7)
        if data is None:
            return None
        return self._parse_json(self._extract_text(data))

    # --- lote de ofertas (modo principal) --------------------------------------
    def process_batch(self, deals: list) -> Optional[list]:
        """Analiza un lote en una sola llamada. Lista de dicts {"i": 1..N, ...}."""
        if not deals:
            return []
        data = self._generate(self._prompt_batch(deals), temperature=0.7)
        if data is None:
            return None
        parsed = self._parse_json(self._extract_text(data))
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):  # a veces envuelve el array en un objeto
            for v in parsed.values():
                if isinstance(v, list):
                    return v
        return None

    # --- prompts ---------------------------------------------------------------
    def _prompt(self, deal: Deal) -> str:
        cabecera = _INSTRUCCIONES.format(categorias=", ".join(category_names()))
        return cabecera + self._ficha(deal, None)

    def _prompt_batch(self, deals: list) -> str:
        cabecera = _INSTRUCCIONES_LOTE.format(
            n=len(deals), categorias=", ".join(category_names())
        )
        return cabecera + "".join(self._ficha(d, n) for n, d in enumerate(deals, start=1))

    @staticmethod
    def _ficha(d: Deal, num: Optional[int]) -> str:
        titulo = f"--- OFERTA {num} ---" if num else "--- OFERTA ---"
        rating = (f"{d.rating} de 5 estrellas" if d.rating
                  else "sin datos (oferta popular en la comunidad)")
        return (
            f"\n\n{titulo}\n"
            f"Título: {d.title}\n"
            f"Precio actual: {d.price_new} {d.currency} (antes {d.price_old})\n"
            f"Descuento: {d.discount_pct}%\n"
            f"Valoración: {rating}\n"
            f"Categoría sugerida (orientativa): {d.category or 'ninguna'}"
        )

    # --- parseo ----------------------------------------------------------------
    @staticmethod
    def _extract_text(data: dict) -> str:
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _parse_json(text: str):
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"[\[{].*[\]}]", text, re.S)  # por si viene envuelto
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    return None
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GeminiBrain":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
