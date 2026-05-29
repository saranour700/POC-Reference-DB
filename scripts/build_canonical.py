#!/usr/bin/env python3
"""Build canonical product entities by linking Voila with Aliments du Québec."""

import json
import re
import sys
import uuid
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path("data")
VOILA = DATA_DIR / "voila_enriched_v2.parquet"
OUTPUT_JSONL = DATA_DIR / "canonical_products.jsonl"
OUTPUT_PARQUET = DATA_DIR / "canonical_products.parquet"

THRESHOLD = 75
NUTRITION_COLS = ["calories", "protein_g", "fat_g", "carbohydrate_g", "sodium_mg"]
ADQ_MATCH_COLS = ["name", "brand", "certification", "subcategory"]

SIZE_RE = re.compile(r"\d+[\.,]?\d*\s*(g|kg|ml|l|oz|lb|count|each|ea|piece|pieces|sheet|sheets|roll|rolls|tablet|tablets|capsule|capsules|pack|packs|tray|tub|jar|bottle|bag|box|can|pouch)\b", re.IGNORECASE)

PUNCT_RE = re.compile(r"[^\w\s'-]")

MULTI_WS = re.compile(r"\s+")

WEAK_TOKENS = {
    "original", "traditionnelle", "traditionnel", "traditional",
    "classic", "classique", "premium", "select", "deluxe",
    "style", "nature", "naturel", "extra", "plus", "ultra",
    "super", "fine", "rich", "riche", "light", "léger",
    "old", "new", "nouveau", "nouvelle", "grand", "petit",
    "special", "spécial", "supreme", "suprême",
    "originale", "traditionnelle", "naturelle", "classique",
}


def normalize_for_match(name: str, brand: str | None = None) -> str:
    s = name.lower().strip()
    if brand:
        b = brand.lower().strip()
        if s.startswith(b):
            candidate = s[len(b):].strip()
            if len(candidate) >= 3:
                s = candidate
    s = SIZE_RE.sub("", s)
    s = PUNCT_RE.sub(" ", s)
    s = MULTI_WS.sub(" ", s).strip()
    return s


def load_adq():
    from datasets import load_dataset
    ds = load_dataset("saraNour/alimentsduquebec-products", split="train")
    data = []
    for i in range(len(ds)):
        row = ds[i]
        data.append({
            "name": row["name"],
            "brand": row["brand"],
            "certification": row["certification"],
            "subcategory": row["subcategory"],
            "url": row["url"],
        })
    return data


def main():
    print("Loading Voila enriched...")
    df = pd.read_parquet(VOILA)
    print(f"  Rows: {len(df)}")

    print("Loading ADQ products...")
    adq_products = load_adq()
    print(f"  ADQ products: {len(adq_products)}")

    # Pre-compute ADQ normalized names
    print("  Normalizing ADQ names...")
    adq_normalized = []
    for p in adq_products:
        n = normalize_for_match(p["name"], p["brand"])
        adq_normalized.append(n)

    # ── STEP 1: Fuzzy match (token_sort_ratio, threshold=75, min_len=5) ──
    print(f"\nSTEP 1 — Fuzzy matching (token_sort_ratio, threshold={THRESHOLD}, min_len=5)...")
    match_results: list[tuple[int, float] | None] = []
    total = len(df)

    # Pre-filter ADQ: build list of (index, norm) where norm >= 5 chars
    adq_candidates = [(j, a) for j, a in enumerate(adq_normalized) if len(a) >= 5]
    print(f"  ADQ candidates (norm >= 5 chars): {len(adq_candidates)}/{len(adq_products)}")

    for idx, row in df.iterrows():
        voila_name = row["product_name"]
        voila_brand = row.get("brand")
        v_norm = normalize_for_match(voila_name, voila_brand)
        if len(v_norm) < 5:
            match_results.append(None)
            continue

        best_score = 0.0
        best_adq = None
        for j, a_norm in adq_candidates:
            score = fuzz.token_sort_ratio(v_norm, a_norm)
            # Reject single-token matches that aren't exact
            if score < 100 and len(v_norm.split()) <= 1 and len(a_norm.split()) <= 1:
                continue
            # Reject weak-token-only matches below 85
            if score < 85:
                v_tokens = set(v_norm.split())
                a_tokens = set(a_norm.split())
                common = v_tokens & a_tokens
                if common and common.issubset(WEAK_TOKENS):
                    continue
            if score > best_score:
                best_score = score
                best_adq = j

        if best_score >= THRESHOLD:
            match_results.append((best_adq, best_score))
        else:
            match_results.append(None)

        if (idx + 1) % 1000 == 0:
            print(f"  Processed {idx + 1}/{total}...")

    matches_found = sum(1 for m in match_results if m is not None)
    print(f"  Matches found: {matches_found}/{total} ({matches_found/total*100:.1f}%)")

    if matches_found:
        print("\n  Sample matches:")
        shown = 0
        for idx, mr in enumerate(match_results):
            if mr is not None:
                adq_idx, score = mr
                row = df.iloc[idx]
                v_norm = normalize_for_match(row["product_name"], row.get("brand"))
                a_norm = adq_normalized[adq_idx]
                print(f"    [TO={score:.0f}] {v_norm:45s} <-> {a_norm}")
                shown += 1
                if shown >= 10:
                    break

    # ── STEP 2: Build canonical entities ──
    print(f"\nSTEP 2 — Building canonical entities...")
    canonical = []
    for idx, row in df.iterrows():
        mr = match_results[idx]
        nutrition = {}
        for col in NUTRITION_COLS:
            val = row.get(col)
            if pd.notna(val):
                nutrition[col] = float(val)

        entity = {
            "canonical_id": str(uuid.uuid4()),
            "name": row["product_name"],
            "brand": row.get("brand"),
            "price_cad": row.get("price_cad"),
            "size_value": row.get("size_value"),
            "size_unit": row.get("size_unit"),
            "pack_type": row.get("pack_type"),
            "language": row.get("language"),
            "image_url": row.get("image_url"),
            "url_voila": row.get("source_url"),
            "category": row.get("category"),
            "is_available": bool(row.get("is_available", True)),
            "nutrition": nutrition,
            "adq_match": None,
            "sources": ["voila"],
        }

        if mr is not None:
            adq_idx, score = mr
            adq = adq_products[adq_idx]
            entity["adq_match"] = {
                "matched": True,
                "adq_name": adq["name"],
                "adq_brand": adq["brand"],
                "adq_certification": adq["certification"],
                "adq_subcategory": adq["subcategory"],
                "match_score": score,
            }
            entity["sources"].append("alimentsduquebec")

        canonical.append(entity)

    # ── STEP 3: Save ──
    print(f"\nSTEP 3 — Saving...")
    with open(OUTPUT_JSONL, "w") as f:
        for ent in canonical:
            f.write(json.dumps(ent, ensure_ascii=False, default=str) + "\n")
    print(f"  Saved {OUTPUT_JSONL} ({len(canonical)} lines)")

    # Convert to DataFrame for parquet — flatten nutrition and adq_match
    flat = []
    for ent in canonical:
        row = {k: v for k, v in ent.items() if k not in ("nutrition", "adq_match", "sources")}
        for nk in NUTRITION_COLS:
            row[f"nutri_{nk}"] = ent["nutrition"].get(nk)
        row["sources"] = ",".join(ent["sources"])
        if ent["adq_match"]:
            for ak in ADQ_MATCH_COLS:
                row[f"adq_{ak}"] = ent["adq_match"].get(f"adq_{ak}")
            row["adq_score"] = ent["adq_match"]["match_score"]
            row["adq_matched"] = True
        else:
            for ak in ADQ_MATCH_COLS:
                row[f"adq_{ak}"] = None
            row["adq_score"] = None
            row["adq_matched"] = False
        flat.append(row)

    pdf = pd.DataFrame(flat)
    pdf.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"  Saved {OUTPUT_PARQUET} ({len(pdf)} rows, {len(pdf.columns)} cols)")

    # ── STEP 4: Report ──
    print(f"\n{'='*60}")
    print("📋 CANONICAL ENTITIES REPORT")
    print("=" * 60)
    total = len(canonical)
    matched_adq = sum(1 for e in canonical if e["adq_match"] and e["adq_match"]["matched"])
    has_nutrition = sum(1 for e in canonical if e["nutrition"])
    has_cat = sum(1 for e in canonical if e.get("category"))
    has_size = sum(1 for e in canonical if e.get("size_value") is not None)
    multi_source = sum(1 for e in canonical if len(e["sources"]) > 1)

    print(f"  Total canonical entities:            {total}")
    print(f"  Matched with alimentsduquebec:       {matched_adq} ({matched_adq/total*100:.1f}%)")
    print(f"  Have nutrition data:                 {has_nutrition} ({has_nutrition/total*100:.1f}%)")
    print(f"  Have category:                       {has_cat} ({has_cat/total*100:.1f}%)")
    print(f"  Have size:                           {has_size} ({has_size/total*100:.1f}%)")
    print(f"  Multi-source (voila + adq):          {multi_source}")


if __name__ == "__main__":
    main()
