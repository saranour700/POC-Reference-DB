#!/usr/bin/env python3
"""Phase 3 v2 — Fixed attribute extraction for Voila normalized data."""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
INPUT = DATA_DIR / "voila_normalized.parquet"
OUTPUT = DATA_DIR / "voila_enriched_v2.parquet"

FRENCH_ACCENT_RE = re.compile(r"[éèêàùûîôçÉÈÊÀÙÛÎÔÇ]")

PACK_TYPE_RE = re.compile(
    r"\b(bottl|can\b|cans\b|bag\b|box\b|boxes\b|pack\b|tray\b|tube\b|jar\b|"
    r"tablet\b|tablets\b|capsule\b|capsules\b|piece\b|pieces\b|"
    r"ea\b|each\b|count\b|tin\b|pouch\b|carton\b|tub\b|brick\b|jug\b)",
    re.IGNORECASE,
)

PACK_TYPE_LABEL = {
    "bottl": "bottle",
    "can": "can",
    "cans": "can",
    "bag": "bag",
    "box": "box",
    "boxes": "box",
    "pack": "pack",
    "tray": "tray",
    "tube": "tube",
    "jar": "jar",
    "tablet": "tablet",
    "tablets": "tablet",
    "capsule": "capsule",
    "capsules": "capsule",
    "piece": "piece",
    "pieces": "piece",
    "ea": "each",
    "each": "each",
    "count": "count",
    "tin": "tin",
    "pouch": "pouch",
    "carton": "carton",
    "tub": "tub",
    "brick": "brick",
    "jug": "jug",
}

SIZE_PARSE_RE = re.compile(
    r"^(\d+)\s*x\s*([\d\.,]+)\s*(g|kg|ml|l|L|oz|lb)\b", re.IGNORECASE
)

SIZE_SIMPLE_RE = re.compile(
    r"^([\d\.,]+)\s*(g|kg|ml|l|L|oz|lb|count|each|ea|per\s*pack|pack|sheet|sheets|roll|rolls|piece|pieces|strip|tray|bag|bottle|can|box|tablet|capsule|gummy|serving|wipe|tissue|liner|liners)\b",
    re.IGNORECASE,
)

SIZE_UNIT_MAP = {
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
    "per_pack": "count",
    "pack": "count",
    "sheet": "sheets",
    "sheets": "sheets",
    "roll": "rolls",
    "rolls": "rolls",
    "piece": "pieces",
    "pieces": "pieces",
    "strip": "strips",
    "tray": "trays",
    "bag": "count",
    "bottle": "bottles",
    "can": "cans",
    "box": "boxes",
    "tablet": "tablets",
    "capsule": "capsules",
    "gummy": "gummies",
    "serving": "servings",
    "wipe": "wipes",
    "tissue": "tissues",
    "liner": "liners",
    "liners": "liners",
}


def standardize_unit(u: str) -> str:
    return SIZE_UNIT_MAP.get(u.lower(), u)


def load_madeinca_brands() -> set[str]:
    from datasets import load_dataset

    ds = load_dataset("saraNour/madeinca-canadian-brands", split="train")
    return set(b.strip().lower() for b in ds["brand"])


def is_canadian_brand(brand: str | None, canadian_brands: set[str]) -> bool:
    if not brand:
        return False
    b = brand.strip().lower()
    if not b:
        return False
    return b in canadian_brands


def detect_language(name: str) -> str:
    if not name:
        return "en"
    has_french = bool(FRENCH_ACCENT_RE.search(name))
    if has_french:
        return "fr"
    return "en"


def detect_pack_type(name: str) -> str | None:
    if not name:
        return None
    m = PACK_TYPE_RE.search(name)
    if m:
        raw = m.group(0).lower()
        return PACK_TYPE_LABEL.get(raw, raw)
    return None


def parse_size(raw: str | None):
    if not raw or not raw.strip():
        return None, None, None
    s = raw.strip()

    m = SIZE_PARSE_RE.match(s)
    if m:
        pack_count = int(m.group(1))
        raw_val = m.group(2).replace(",", "")
        raw_unit = m.group(3)
        try:
            val = float(raw_val)
        except ValueError:
            return None, None, None
        unit = standardize_unit(raw_unit)
        return val, unit, pack_count

    m = SIZE_SIMPLE_RE.match(s)
    if m:
        raw_val = m.group(1).replace(",", "")
        raw_unit = m.group(2)
        try:
            val = float(raw_val)
        except ValueError:
            return None, None, None
        unit = standardize_unit(raw_unit)
        return val, unit, None

    return None, None, None


def main():
    print("Loading normalized parquet...")
    df = pd.read_parquet(INPUT)
    print(f"  Rows: {len(df)}, Cols: {len(df.columns)}")

    # ── 1. Brand detection (exact match only) ──
    print("\n[1/5] Brand detection (exact match)...")
    canadian_brands = load_madeinca_brands()
    print(f"  Loaded {len(canadian_brands)} Canadian brands from madeinca")

    matched_brands = set()
    for b in df["brand"].dropna().unique():
        stripped = b.strip().lower()
        if stripped in canadian_brands:
            matched_brands.add(stripped)
    print(f"  Unique brands matched: {len(matched_brands)}")
    print(f"  Matched brands: {sorted(matched_brands)}")

    df["is_canadian_brand"] = df["brand"].apply(
        lambda b: is_canadian_brand(b, canadian_brands)
    )
    canadian_count = df["is_canadian_brand"].sum()
    total = len(df)
    print(f"  Products matched: {canadian_count}/{total} ({canadian_count/total*100:.1f}%)")

    # ── 2. Size normalization ──
    print("\n[2/5] Size normalization...")
    parsed = df["size"].apply(parse_size)
    df["size_value"] = parsed.apply(lambda x: x[0])
    df["size_unit"] = parsed.apply(lambda x: x[1])
    df["pack_count"] = parsed.apply(lambda x: x[2])
    size_ok = df["size_value"].notna().sum()
    print(f"  Size extracted: {size_ok}/{total} ({size_ok/total*100:.1f}%)")
    mc_count = df["pack_count"].notna().sum()
    print(f"  Multipack (pack_count > 0): {mc_count}")

    # ── 3. Pack type detection ──
    print("\n[3/5] Pack type detection...")
    df["pack_type"] = df["product_name"].apply(detect_pack_type)
    pt_count = df["pack_type"].notna().sum()
    print(f"  Pack type detected: {pt_count}/{total} ({pt_count/total*100:.1f}%)")
    print(f"  Distribution:")
    for pt, cnt in df["pack_type"].value_counts().items():
        print(f"    {pt}: {cnt}")

    # ── 4. Language detection ──
    print("\n[4/5] Language detection...")
    df["language"] = df["product_name"].apply(detect_language)
    lang_counts = df["language"].value_counts()
    for lang in ["en", "fr"]:
        cnt = lang_counts.get(lang, 0)
        print(f"  {lang}: {cnt} ({cnt/total*100:.1f}%)")

    # ── 5. Category cleanup ──
    print("\n[5/5] Category cleanup...")
    orig_null = df["category"].isna().sum() + (df["category"] == "").sum()
    df["category"] = df["category"].apply(
        lambda c: c.strip().title() if isinstance(c, str) and c.strip() else None
    )
    remaining_null = df["category"].isna().sum()
    print(f"  Category nulls before: {orig_null}")
    print(f"  Category nulls after:  {remaining_null}")

    # Drop Phase 2 temp column
    if "category_missing" in df.columns:
        df = df.drop(columns=["category_missing"])

    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False)
    print(f"\nSaved → {OUTPUT}  ({len(df)} rows, {len(df.columns)} cols)")

    # ── Report ──
    print(f"\n{'='*60}")
    print("📋 EXTRACTION REPORT (v2)")
    print("=" * 60)
    matched = df["is_canadian_brand"].sum()
    print(f"  is_canadian_brand:             {matched} ({matched/total*100:.1f}%)")
    print(f"    unique brands matched:       {len(matched_brands)} ({sorted(matched_brands)})")
    size_pct = df["size_value"].notna().sum() / total * 100
    print(f"  size extracted successfully:    {size_pct:.1f}%")
    pt_pct = df["pack_type"].notna().sum() / total * 100
    print(f"  pack_type detected:            {pt_pct:.1f}%")
    for lang in ["en", "fr"]:
        cnt = lang_counts.get(lang, 0)
        print(f"  language {lang}:                   {cnt} ({cnt/total*100:.1f}%)")
    cat_null = df["category"].isna().sum()
    print(f"  category nulls remaining:      {cat_null} ({cat_null/total*100:.1f}%)")
    print(f"\n  Columns added: is_canadian_brand, pack_count, pack_type, language")


if __name__ == "__main__":
    main()
