# POC-Reference-DB

Reference database of Canadian food products. Scrapes, normalizes, enriches, and links products from multiple Canadian grocery sources.

## Datasets

| Source | Products | Nutrition | HF Dataset |
|--------|----------|-----------|------------|
| Voila Compliments | 4,440 | 2,935 | [`voila-compliments-products`](https://huggingface.co/datasets/saraNour/voila-compliments-products) |
| Voila Nutrition | 2,935 | — | [`voila-compliments-nutrition`](https://huggingface.co/datasets/saraNour/voila-compliments-nutrition) |
| Voila Enriched | 4,440 | 2,935 | [`voila-compliments-enriched`](https://huggingface.co/datasets/saraNour/voila-compliments-enriched) |
| Aliments du Québec | 4,390 | — | [`alimentsduquebec-products`](https://huggingface.co/datasets/saraNour/alimentsduquebec-products) |
| MadeInCA Brands | 468 | — | [`madeinca-canadian-brands`](https://huggingface.co/datasets/saraNour/madeinca-canadian-brands) |
| Canonical Products | 4,440 | 2,779 | [`canonical-products`](https://huggingface.co/datasets/saraNour/canonical-products) |
| Sobeys Compliments | 345 | 345 | [`sobeys-compliments-products`](https://huggingface.co/datasets/saraNour/sobeys-compliments-products) |

## Pipeline

```
Scrape → Raw JSON → normalize_voila.py → enrich_voila.py → build_canonical.py → FastAPI
```

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --source compliments
```

### FastAPI Server

```bash
.venv/bin/uvicorn api.main:app --reload
# → http://localhost:8000/docs
```

| Endpoint | Description |
|----------|-------------|
| `GET /products` | Search, filter by category/nutrition/availability |
| `GET /products/{id}` | Full product detail with nutrition + ADQ match |
| `GET /categories` | Unique categories with product counts |
| `GET /stats` | Aggregate statistics |

## Phases

| Phase | Script | Output |
|-------|--------|--------|
| 1 — Scrape | `scrapers/compliments/scraper.py` | `compliments_full.json` (4,440 products) |
| 1 — Nutrition | `scrapers/compliments/scraper.py` | `compliments_nutrition_full.json` (2,935 records) |
| 2 — Normalize | `scripts/normalize_voila.py` | `voila_normalized.parquet` (join products + nutrition) |
| 3 — Enrich | `scripts/enrich_voila_v2.py` | `voila_enriched_v2.parquet` (brand/pack/language) |
| 4 — Canonical | `scripts/build_canonical.py` | `canonical_products.parquet` (fuzzy match Voila + ADQ) |

## Upload to Hugging Face

```bash
echo "HUGGINGFACE_TOKEN=hf_xxx" >> .env
python3 main.py --source compliments --upload-hf
```

## Project Structure

```
├── api/                # FastAPI application
├── scrapers/           # Web scrapers (compliments, sobeys, alimentsduquebec, madeinca)
├── scripts/            # Normalization, enrichment, canonical entity builder
├── pipelines/          # dlt ingestion + transformation + loading
├── storage/            # HuggingFace upload
├── schemas/            # Data schemas
├── utils/              # Logging, config, IO, retry
├── configs/            # YAML config files
├── data/               # Raw / processed parquet / exports
└── tests/              # Unit + integration tests
```

## Sources

- **Voila:** `voila.ca` — 4,440 Compliments products via sitemap + product page scraping
- **Aliments du Québec:** `alimentsduquebec.com` — 4,390 certified-Québec products
- **MadeInCA:** `madeinca.ca/grocery-store-guide/` — 468 Canadian brands
- **Sobeys:** `sobeys.com` — 345 Compliments products
