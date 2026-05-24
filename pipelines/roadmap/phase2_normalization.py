import re, json
from pathlib import Path
from typing import Any
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase2")

UNIT_MAP = {
    "millilitre": "ml", "milliliter": "ml", "millilitres": "ml", "milliliters": "ml",
    "litre": "ml", "liter": "ml", "litres": "ml", "liters": "ml",
    "l": "ml",
    "gram": "g", "grams": "g",
    "kilogram": "g", "kilograms": "g", "kg": "g",
    "ounce": "g", "ounces": "g", "oz": "g",
    "pound": "g", "pounds": "g", "lb": "g",
    "pack": "count", "pk": "count", "ea": "count", "each": "count",
    "count": "count",
}

ABBREVIATIONS = {
    "org": "organic",
    "orig": "original",
    "nat": "natural",
    "unsalted": "no salt",
    "unsweetened": "no sugar",
    "unsw": "no sugar",
    "w/": "with",
    "w/o": "without",
}

def normalize_text(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower().strip()
    t = re.sub(r'[^\w\s/\\\-.]', '', t)
    t = re.sub(r'\s+', ' ', t)
    for abbr, full in ABBREVIATIONS.items():
        t = re.sub(r'\b' + re.escape(abbr) + r'\b', full, t)
    return t.strip()


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = unit.lower().strip().rstrip('.')
    return UNIT_MAP.get(u, u)


def normalize_quantity_text(qty_text: str | None) -> str | None:
    if not qty_text:
        return None
    return normalize_text(qty_text)


def run(staging: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 2: Text Normalization Layer")
    logger.info("=" * 60)

    normalized = {}

    for source_key in ["stg_compliments_products", "stg_sobeys_products"]:
        products = staging.get(source_key, [])
        out = []
        for p in products:
            n = dict(p)
            for text_field in ["product_name", "brand", "category", "description"]:
                if text_field in n:
                    n[f"{text_field}_raw"] = n[text_field]
                    n[text_field] = normalize_text(n.get(text_field))
            out.append(n)
        normalized[source_key] = out
        logger.info(f"  {source_key}: {len(out)} products normalized")

    for source_key in ["stg_nutrition_voila", "stg_nutrition_sobeys"]:
        records = staging.get(source_key, [])
        out = []
        for r in records:
            n = dict(r)
            if "serving_size" in n:
                n["serving_size_raw"] = n["serving_size"]
                n["serving_size_normalized"] = normalize_text(n["serving_size"])
            out.append(n)
        normalized[source_key] = out
        logger.info(f"  {source_key}: {len(out)} nutrition records normalized")

    save_dir = Path("data/normalized")
    save_dir.mkdir(parents=True, exist_ok=True)
    for name, data in normalized.items():
        with open(save_dir / f"{name}.json", "w") as f:
            json.dump(data, f, indent=2)

    logger.info("=" * 60)
    logger.info("PHASE 2 COMPLETE")
    logger.info("=" * 60)
    return normalized
