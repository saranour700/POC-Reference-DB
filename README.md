# POC-Reference-DB

Reference DB — Proof of Concept. Scraping pipeline for Canadian food product data (Compliments brand from Voila + Sobeys).

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 main.py --source compliments
```

## Datasets

| Source | Products | Nutrition | HF Dataset |
|--------|----------|-----------|------------|
| Voila | 300 | 299 | [compliments-products](https://huggingface.co/datasets/saraNour/compliments-products) |
| Sobeys | 345 | 345 | [sobeys-compliments-products](https://huggingface.co/datasets/saraNour/sobeys-compliments-products) |

## Upload to Hugging Face

```bash
echo "HUGGINGFACE_TOKEN=hf_xxx" >> .env
python3 main.py --source compliments --upload-hf
python3 main.py --source sobeys --upload-hf
```

## Project Structure

```
├── scrapers/          # Web scrapers (compliments, sobeys, smartlabel, alimentsduquebec)
├── pipelines/         # dlt ingestion + transformation + loading
├── storage/           # DuckDB + HuggingFace
├── schemas/           # Data schemas
├── utils/             # Logging, config, IO, retry, validators
├── configs/           # YAML config files
├── data/              # Raw / staged / processed / exports
└── tests/             # Unit + integration tests
```

## Data Flow

```
Scrape (voila.ca / sobeys.com) → Raw JSON → dlt → DuckDB → HuggingFace Datasets
```

## Sources

- **Voila:** `https://voila.ca/categories?brands=Compliments` — 300 products via `__INITIAL_STATE__` + GraphQL
- **Sobeys:** `https://www.sobeys.com/products/{slug}` — 345 products via ld+json schema.org data
