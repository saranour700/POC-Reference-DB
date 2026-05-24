import re, json
from pathlib import Path
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase4")


def build_core_key(attrs: dict) -> str:
    parts = [
        (attrs.get("brand") or "").lower().strip(),
        (attrs.get("product_type") or "").lower().strip(),
        (attrs.get("flavor") or "").lower().strip(),
        (attrs.get("formula") or "").lower().strip(),
    ]
    parts = [p for p in parts if p]
    return " | ".join(parts)


def build_variant_key(attrs: dict) -> str:
    parts = [
        str(attrs.get("quantity_raw") or ""),
        (attrs.get("unit") or "").lower().strip(),
        (attrs.get("packaging") or "").lower().strip(),
        str(attrs.get("count") or ""),
    ]
    parts = [p for p in parts if p and p != "None"]
    return " | ".join(parts) if parts else "default"


def run(parsed: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 4: Core Product vs Variant Modeling")
    logger.info("=" * 60)

    all_parsed = parsed.get("parsed_products", [])

    core_groups = defaultdict(list)
    variant_groups = defaultdict(list)

    for p in all_parsed:
        core_key = build_core_key(p)
        variant_key = build_variant_key(p)
        pid = p.get("product_id") or f"unknown-{hash(core_key + variant_key)}"
        core_groups[core_key].append({**p, "_variant_key": variant_key})

    canonical_products = []
    product_variants = []
    variant_index = {}

    canonical_seq = 0
    variant_seq = 0

    for core_key, products in core_groups.items():
        canonical_seq += 1
        canonical_id = f"CP{canonical_seq:04d}"

        first = products[0]
        canonical_products.append({
            "canonical_id": canonical_id,
            "brand": first.get("brand"),
            "product_type": first.get("product_type"),
            "flavor": first.get("flavor"),
            "formula": first.get("formula"),
            "core_key": core_key,
            "variant_count": len(products),
            "sources": list(set(p.get("source", "") for p in products)),
        })

        for p in products:
            variant_seq += 1
            variant_id = f"VAR{variant_seq:04d}"
            quantity = p.get("quantity_raw")
            price = None

            product_variants.append({
                "variant_id": variant_id,
                "canonical_id": canonical_id,
                "product_id": p.get("product_id"),
                "source": p.get("source"),
                "quantity": quantity,
                "unit": p.get("unit"),
                "packaging": p.get("packaging"),
                "count": p.get("count"),
                "product_type": p.get("product_type"),
                "flavor": p.get("flavor"),
                "formula": p.get("formula"),
            })
            variant_index[p.get("product_id")] = variant_id

    with_type = sum(1 for c in canonical_products if c["product_type"])
    multi_variant = sum(1 for c in canonical_products if c["variant_count"] > 1)
    logger.info(f"  Canonical products: {len(canonical_products)} ({with_type} with type)")
    logger.info(f"  Product variants: {len(product_variants)}")
    logger.info(f"  Multi-variant cores: {multi_variant}")
    logger.info(f"  Avg variants/core: {len(product_variants)/max(len(canonical_products),1):.1f}")

    save_dir = Path("data/canonical")
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(save_dir / "canonical_products.json", "w") as f:
        json.dump(canonical_products, f, indent=2)
    with open(save_dir / "product_variants.json", "w") as f:
        json.dump(product_variants, f, indent=2)
    with open(save_dir / "variant_index.json", "w") as f:
        json.dump(variant_index, f, indent=2)

    logger.info(f"  Saved → data/canonical/")

    logger.info("=" * 60)
    logger.info("PHASE 4 COMPLETE")
    logger.info("=" * 60)

    return {
        "canonical_products": canonical_products,
        "product_variants": product_variants,
        "variant_index": variant_index,
    }
