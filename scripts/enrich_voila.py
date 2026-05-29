#!/usr/bin/env python3
"""Phase 3 — Attribute extraction & enrichment for Voila normalized data."""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
INPUT = DATA_DIR / "voila_normalized.parquet"
OUTPUT = DATA_DIR / "voila_enriched.parquet"

FRENCH_ACCENT_RE = re.compile(r"[éèêàùûîôçÉÈÊÀÙÛÎÔÇ]")

PACK_TYPE_RE = re.compile(
    r"\b(bottle|can|bag|box|pack|tray|tube|jar|tub|pouch|carton|tin|brick|jug)\b",
    re.IGNORECASE,
)

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
    for cb in canadian_brands:
        if b == cb or b.startswith(cb + " ") or b.startswith(cb + "-"):
            return True
    return False


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
    return m.group(1).lower() if m else None


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

    # 1. Brand detection
    print("\n[1/5] Brand detection...")
    canadian_brands = load_madeinca_brands()
    print(f"  Loaded {len(canadian_brands)} Canadian brands from madeinca")
    df["is_canadian_brand"] = df["brand"].apply(
        lambda b: is_canadian_brand(b, canadian_brands)
    )
    canadian_count = df["is_canadian_brand"].sum()
    print(f"  Matched: {canadian_count}/{len(df)} ({canadian_count/len(df)*100:.1f}%)")

    # 2. Size normalization (re-derive from raw 'size' column with pack_count)
    print("\n[2/5] Size normalization...")
    parsed = df["size"].apply(parse_size)
    df["size_value"] = parsed.apply(lambda x: x[0])
    df["size_unit"] = parsed.apply(lambda x: x[1])
    df["pack_count"] = parsed.apply(lambda x: x[2])
    size_ok = df["size_value"].notna().sum()
    print(f"  Size extracted: {size_ok}/{len(df)} ({size_ok/len(df)*100:.1f}%)")
    mc_count = df["pack_count"].notna().sum()
    print(f"  Multipack (pack_count > 0): {mc_count}")

    # 3. Pack type detection
    print("\n[3/5] Pack type detection...")
    df["pack_type"] = df["product_name"].apply(detect_pack_type)
    pt_count = df["pack_type"].notna().sum()
    print(f"  Pack type detected: {pt_count}/{len(df)} ({pt_count/len(df)*100:.1f}%)")
    if pt_count:
        print(f"  Distribution:")
        for pt, cnt in df["pack_type"].value_counts().head(10).items():
            print(f"    {pt}: {cnt}")

    # 4. Language detection
    print("\n[4/5] Language detection...")
    df["language"] = df["product_name"].apply(detect_language)
    lang_counts = df["language"].value_counts()
    for lang in ["en", "fr"]:
        cnt = lang_counts.get(lang, 0)
        print(f"  {lang}: {cnt} ({cnt/len(df)*100:.1f}%)")

    # 5. Category cleanup
    print("\n[5/5] Category cleanup...")
    orig_null = df["category"].isna().sum() + (df["category"] == "").sum()
    df["category"] = df["category"].apply(
        lambda c: c.strip().title() if isinstance(c, str) and c.strip() else ""
    )
    df["category"] = df["category"].replace("", None)
    remaining_null = df["category"].isna().sum()
    print(f"  Category nulls before: {orig_null}")
    print(f"  Category nulls after:  {remaining_null}")

    # Drop temporary category_missing column from Phase 2
    if "category_missing" in df.columns:
        df = df.drop(columns=["category_missing"])

    # Save
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT, index=False)
    print(f"\nSaved to: {OUTPUT}  ({len(df)} rows, {len(df.columns)} cols)")

    # ── Print extraction report ──
    print(f"\n{'='*60}")
    print("📋 EXTRACTION REPORT")
    print("=" * 60)
    total = len(df)

    matched = df["is_canadian_brand"].sum()
    print(f"  is_canadian_brand:             {matched} ({matched/total*100:.1f}%)")

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
