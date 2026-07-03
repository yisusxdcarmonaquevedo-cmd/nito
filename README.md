# Cazador de Chollos 🛒🎯

Sistema automatizado (coste $0) que detecta ofertas de Amazon, las filtra, las
procesa con IA (Gemini Flash) y las publica en una web estática.

## Pipeline

1. **Radar** — fuentes RSS gratuitas (Slickdeals, Reddit) por mercado.
2. **Filtro estático** — dedupe por ASIN (SQLite), descuento ≥30%, rating ≥4★.
3. **Cerebro** — Gemini 2.5 Flash: coherencia + redacción del post.
4. **Monetización + publicación** — enlace de afiliado + web (Cloudflare Pages).

## Estado actual

✅ Bloque 1: esqueleto + adaptador de Slickdeals (Radar, mercado US).

## Estructura

```
config/        settings.yaml (mercados y fuentes), categories.yaml
src/
  models.py    Deal (modelo normalizado, común a toda fuente)
  config.py    carga de settings + fábrica de fuentes
  sources/     un adaptador por fuente (base.py = contrato común)
tests/         pruebas en vivo contra feeds reales
```

## Probar la ingesta en vivo

```bash
python -m pip install -r requirements.txt
python -m tests.test_slickdeals_live
```
