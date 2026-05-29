#!/usr/bin/env python3
"""Phase 2 — Normalize Voila Compliments products + nutrition into a single clean dataset."""

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
OUTPUT = DATA_DIR / "voila_normalized.parquet"

PRODUCTS_FILE = RAW_DIR / "compliments_full.json"
NUTRITION_FILE = RAW_DIR / "compliments_nutrition_full.json"

SPARSE_NUTRI_COLS = [
    "omega6_g",
    "omega3_g",
    "monounsaturated_fat_g",
    "polyunsaturated_fat_g",
    "sugar_alcohols_g",
]


def load_json(path):
    with open(path) as f:
        return json.load(f)


def normalize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r" +", " ", name)
    return name


def extract_size_from_value(size_raw: str):
    if not size_raw or not size_raw.strip():
        return None, None
    s = size_raw.strip()

    m = re.match(
        r"^([\d\.,]+)\s*(g|kg|ml|l|L|oz|lb|count|each|EA|per pack|sheet|sheets|roll|rolls|pack|packs|tray|trays|bag|bags|bottle|bottles|can|cans|box|boxes|piece|pieces|strip|strips|tablet|tablets|capsule|capsules|gummy|gummies|serving|servings|wipe|wipes|tissue|tissues|sq ft|sqft|liners)\b",
        s,
        re.IGNORECASE,
    )
    if m:
        raw_val = m.group(1).replace(",", "")
        raw_unit = m.group(2).lower()
        try:
            val = float(raw_val)
        except ValueError:
            return None, None
        unit = standardize_unit(raw_unit)
        return val, unit

    m2 = re.match(r"^(\d+)\s*x\s*([\d\.,]+)\s*(g|kg|ml|l|L|oz|lb)\b", s, re.IGNORECASE)
    if m2:
        multiplier = float(m2.group(1))
        single = float(m2.group(2).replace(",", ""))
        raw_unit = m2.group(3).lower()
        val = round(multiplier * single, 2)
        unit = standardize_unit(raw_unit)
        return val, unit

    return None, None


def extract_size_from_name(product_name: str):
    name = product_name.strip()
    m = re.search(
        r"(\d+[\.,]?\d*)\s*(g|kg|ml|l|L|oz|lb|count|sheet|sheets|roll|rolls|tray|trays|bag|bags|bottle|bottles|can|cans|box|boxes|piece|pieces|strip|strips|tablet|tablets|capsule|capsules|gummy|gummies|serving|servings|wipe|wipes|tissue|tissues|sq ft|sqft|liners)\b",
        name,
        re.IGNORECASE,
    )
    if m:
        raw_val = m.group(1).replace(",", "")
        raw_unit = m.group(2).lower()
        try:
            val = float(raw_val)
        except ValueError:
            return None, None
        unit = standardize_unit(raw_unit)
        return val, unit
    return None, None


def standardize_unit(u: str) -> str:
    mapping = {
        "ml": "ml",
        "l": "L",
        "g": "g",
        "kg": "kg",
        "oz": "oz",
        "lb": "lb",
        "count": "count",
        "each": "count",
        "ea": "count",
        "per pack": "count",
        "pack": "count",
        "packs": "count",
        "sheet": "sheets",
        "sheets": "sheets",
        "roll": "rolls",
        "rolls": "rolls",
        "tray": "trays",
        "trays": "trays",
        "bag": "count",
        "bags": "count",
        "bottle": "bottles",
        "bottles": "bottles",
        "can": "cans",
        "cans": "cans",
        "box": "boxes",
        "boxes": "boxes",
        "piece": "pieces",
        "pieces": "pieces",
        "strip": "strips",
        "strips": "strips",
        "tablet": "tablets",
        "tablets": "tablets",
        "capsule": "capsules",
        "capsules": "capsules",
        "gummy": "gummies",
        "gummies": "gummies",
        "serving": "servings",
        "servings": "servings",
        "wipe": "wipes",
        "wipes": "wipes",
        "tissue": "tissues",
        "tissues": "tissues",
        "sq ft": "sq_ft",
        "sqft": "sq_ft",
        "liner": "liners",
        "liners": "liners",
    }
    return mapping.get(u, u)


def main():
    print("Loading products...")
    products = load_json(PRODUCTS_FILE)
    print(f"  Products: {len(products)}")

    print("Loading nutrition...")
    nutrition = load_json(NUTRITION_FILE)
    print(f"  Nutrition records: {len(nutrition)}")

    # Convert to DataFrames
    pdf = pd.DataFrame(products)
    ndf = pd.DataFrame(nutrition)

    # Drop the useless product_id from nutrition
    ndf = ndf.drop(columns=["product_id"], errors="ignore")

    # Join on retailer_product_id
    merged = pdf.merge(ndf, on="retailer_product_id", how="left", suffixes=("", "_nutri"))

    # Drop any _nutri suffixed columns (from duplicate column names)
    nutri_cols = [c for c in merged.columns if c.endswith("_nutri")]
    merged = merged.drop(columns=nutri_cols)

    matched = merged["calories"].notna().sum()
    print(f"  Products with nutrition matched: {matched} / {len(merged)} ({matched / len(merged) * 100:.1f}%)")

    # Normalize product_name
    merged["name_clean"] = merged["product_name"].apply(normalize_name)

    # Normalize size
    size_fallback_used = 0
    size_values = []
    size_units = []
    for _, row in merged.iterrows():
        val, unit = extract_size_from_value(row.get("size"))
        if val is not None and unit is not None:
            size_values.append(val)
            size_units.append(unit)
        else:
            # Try fallback from product name
            name = row.get("product_name", "")
            val2, unit2 = extract_size_from_name(name)
            if val2 is not None and unit2 is not None:
                size_values.append(val2)
                size_units.append(unit2)
                size_fallback_used += 1
            else:
                size_values.append(None)
                size_units.append(None)

    merged["size_value"] = size_values
    merged["size_unit"] = size_units

    # Flag missing categories
    merged["category_missing"] = merged["category"].isna() | (merged["category"] == "")

    # Print sparsity for sparse nutrition columns
    print(f"\n  Sparse nutrition columns (>90% null):")
    for col in SPARSE_NUTRI_COLS:
        if col in merged.columns:
            null_pct = merged[col].isna().sum() / len(merged) * 100
            print(f"    {col}: {null_pct:.1f}% null")
        else:
            print(f"    {col}: <column not found>")

    products_no_nutrition = merged["calories"].isna().sum()
    print(f"\n  Products WITHOUT nutrition (likely non-food): {int(products_no_nutrition)}")
    print(f"  Size extracted from name (fallback used): {size_fallback_used}")

    # Ensure output dir exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Save as parquet
    merged.to_parquet(OUTPUT, index=False)
    print(f"\nSaved to: {OUTPUT}  ({len(merged)} rows, {len(merged.columns)} cols)")

    # Print report
    print(f"\n{'='*60}")
    print(f"📋 JOIN REPORT")
    print(f"{'='*60}")
    print(f"  Total products:               {len(merged)}")
    print(f"  Products with nutrition:       {int(matched)} ({matched / len(merged) * 100:.1f}%)")
    print(f"  Products without nutrition:    {int(products_no_nutrition)}")
    print(f"  Size extracted from name:      {size_fallback_used}")
    print(f"  Columns in output:             {len(merged.columns)}")
    print(f"  Sparse columns flagged:        {len(SPARSE_NUTRI_COLS)}")


if __name__ == "__main__":
    main()
