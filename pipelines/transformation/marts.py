import re, json
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("pipeline.marts")


def extract_numeric_rid(rid: str | None) -> str | None:
    if not rid:
        return None
    m = re.search(r'(\d+)', str(rid))
    return m.group(1) if m else None


def build_canonical_products(int_products: list[dict]) -> list[dict]:
    type_groups = defaultdict(list)
    for p in int_products:
        key = (p.get("product_type") or "").lower().strip()
        if key:
            type_groups[key].append(p)

    canonical = []
    canonical_id = 1
    seen_types = set()

    for product_type, group in type_groups.items():
        if product_type in seen_types:
            continue
        seen_types.add(product_type)

        best = max(group, key=lambda x: 1 if x.get("product_name") else 0)
        canonical.append({
            "canonical_id": f"CMP-{canonical_id:04d}",
            "brand": "Compliments",
            "product_type": best["product_type"],
            "product_name": best["product_name"],
            "description": "",
            "image_url": best.get("image_url"),
            "category": best.get("category"),
            "primary_source": best.get("source", "unknown"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        canonical_id += 1

    # Add products without detected type as "Other"
    for p in int_products:
        pt = (p.get("product_type") or "").lower().strip()
        if not pt or pt == "other":
            canonical.append({
                "canonical_id": f"CMP-{canonical_id:04d}",
                "brand": "Compliments",
                "product_type": "Other",
                "product_name": p["product_name"] if p.get("product_name") else p.get("product_id"),
                "description": "",
                "image_url": p.get("image_url"),
                "category": p.get("category"),
                "primary_source": p.get("source", "unknown"),
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            canonical_id += 1

    logger.info(f"Built {len(canonical)} canonical products")
    return canonical


def assign_canonical_ids(int_products: list[dict], canonical: list[dict]) -> dict:
    type_to_canonical = {}
    for c in canonical:
        pt = (c["product_type"] or "").lower().strip()
        type_to_canonical[pt] = c["canonical_id"]

    product_to_canonical = {}
    for p in int_products:
        pid = p.get("product_id")
        pt = (p.get("product_type") or "").lower().strip()
        if pt in type_to_canonical:
            product_to_canonical[pid] = type_to_canonical[pt]
    return product_to_canonical


def build_variants(int_products: list[dict], product_to_canonical: dict) -> list[dict]:
    variants = []
    for p in int_products:
        pid = p.get("product_id")
        if not pid:
            continue
        qty = p.get("quantity") or 0
        price = p.get("price_cad") or 0
        price_per_unit = round(price / qty, 4) if qty and price else None
        variants.append({
            "variant_id": f"VAR-{pid}",
            "canonical_id": product_to_canonical.get(pid),
            "product_id": pid,
            "source": p.get("source"),
            "product_name": p.get("product_name"),
            "quantity": qty,
            "quantity_unit": p.get("quantity_unit"),
            "pack_count": p.get("pack_count"),
            "price_cad": price or None,
            "price_per_unit": price_per_unit,
            "image_url": p.get("image_url"),
            "is_available": p.get("is_available", True),
        })

    logger.info(f"Built {len(variants)} variants")
    return variants


def build_sources(int_products: list[dict], sobeys_raw: list[dict], product_to_canonical: dict) -> list[dict]:
    source_lookup = {}
    for p in sobeys_raw:
        sku = p.get("sku")
        if sku:
            source_lookup[sku] = {
                "source_url": p.get("sobeys_url"),
                "scraped_at": p.get("scraped_at"),
            }

    sources = []
    for p in int_products:
        pid = p.get("product_id")
        if not pid:
            continue
        src_info = source_lookup.get(pid, {})
        sources.append({
            "product_id": pid,
            "canonical_id": product_to_canonical.get(pid),
            "source": p.get("source"),
            "source_product_id": pid,
            "source_url": src_info.get("source_url") or (f"https://voila.ca/products/_/{pid}" if p.get("source") == "voila" else None),
            "price_cad": p.get("price_cad"),
            "is_available": p.get("is_available", True),
            "scraped_at": src_info.get("scraped_at") or p.get("scraped_at") or datetime.now(timezone.utc).isoformat(),
        })

    logger.info(f"Built {len(sources)} source records")
    return sources


def build_nutrition_mart(int_nutrition: list[dict], product_to_canonical: dict) -> list[dict]:
    nutrition = []
    for n in int_nutrition:
        pid = n.get("product_id")
        nutrition.append({
            "nutrition_id": f"NUT-{pid}",
            "product_id": pid,
            "canonical_id": product_to_canonical.get(pid),
            "serving_size": n.get("serving_size"),
            "calories": n.get("calories"),
            "fat_g": n.get("fat_g"),
            "saturated_fat_g": n.get("saturated_fat_g"),
            "trans_fat_g": n.get("trans_fat_g"),
            "cholesterol_mg": n.get("cholesterol_mg"),
            "sodium_mg": n.get("sodium_mg"),
            "potassium_mg": n.get("potassium_mg"),
            "carbohydrate_g": n.get("carbohydrate_g"),
            "fibre_g": n.get("fibre_g"),
            "sugars_g": n.get("sugars_g"),
            "protein_g": n.get("protein_g"),
            "calcium_mg": n.get("calcium_mg"),
            "iron_mg": n.get("iron_mg"),
            "source": n.get("source"),
        })

    logger.info(f"Built {len(nutrition)} nutrition mart records")
    return nutrition


def run(intermediate: dict, sobeys_raw: list[dict]) -> dict:
    int_products = intermediate.get("int_products", [])

    canonical = build_canonical_products(int_products)
    product_to_canonical = assign_canonical_ids(int_products, canonical)
    variants = build_variants(int_products, product_to_canonical)
    sources = build_sources(int_products, sobeys_raw, product_to_canonical)
    nutrition = build_nutrition_mart(intermediate.get("int_nutrition", []), product_to_canonical)

    return {
        "dim_canonical_products": canonical,
        "dim_product_variants": variants,
        "fct_product_sources": sources,
        "dim_nutrition": nutrition,
    }
