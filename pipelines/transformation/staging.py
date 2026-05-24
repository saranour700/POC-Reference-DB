import json, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("pipeline.staging")


def load_voila_products() -> list[dict[str, Any]]:
    path = Path("data/products_for_nutrition.json")
    if not path.exists():
        logger.error("products_for_nutrition.json not found")
        return []
    with open(path) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} raw Voila products")

    staged = []
    for p in raw:
        staged.append({
            "product_id": p.get("uuid") or p.get("productId"),
            "retailer_product_id": p.get("rid") or p.get("retailerProductId"),
            "slug": p.get("slug"),
            "product_name": p.get("name"),
            "brand": "Compliments",
            "price_cad": p.get("price", {}).get("current", {}).get("amount") if isinstance(p.get("price"), dict) else None,
            "price_currency": "CAD",
            "size": p.get("size", {}).get("value") if isinstance(p.get("size"), dict) else p.get("size"),
            "category": None,
            "image_url": None,
            "is_available": p.get("available", p.get("is_available", True)),
            "source": "voila",
            "source_url": p.get("url"),
            "source_type": p.get("source", "graphql"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        })
    return staged


def load_sobeys_products() -> list[dict[str, Any]]:
    path = Path("data/sobeys_products.json")
    if not path.exists():
        logger.error("sobeys_products.json not found")
        return []
    with open(path) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} raw Sobeys products")

    staged = []
    for p in raw:
        staged.append({
            "sku": p.get("sku"),
            "sobeys_url": p.get("sobeys_url"),
            "brand": p.get("brand", "Compliments"),
            "product_name": p.get("product_name"),
            "description": p.get("description", ""),
            "image_url": p.get("image_url"),
            "price": float(p["price"]) if p.get("price") else None,
            "price_currency": p.get("price_currency", "CAD"),
            "availability": p.get("availability"),
            "source": "sobeys",
            "scraped_at": p.get("scraped_at", datetime.now(timezone.utc).isoformat()),
        })
    return staged


def load_voila_nutrition() -> list[dict[str, Any]]:
    path = Path("data/nutrition_records.json")
    if not path.exists():
        logger.error("nutrition_records.json not found")
        return []
    with open(path) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} raw Voila nutrition records")
    return raw


def load_sobeys_nutrition() -> list[dict[str, Any]]:
    path = Path("data/sobeys_nutrition.json")
    if not path.exists():
        logger.error("sobeys_nutrition.json not found")
        return []
    with open(path) as f:
        raw = json.load(f)
    logger.info(f"Loaded {len(raw)} raw Sobeys nutrition records")
    return raw


def run() -> dict[str, list]:
    return {
        "stg_compliments_products": load_voila_products(),
        "stg_sobeys_products": load_sobeys_products(),
        "stg_nutrition_voila": load_voila_nutrition(),
        "stg_nutrition_sobeys": load_sobeys_nutrition(),
    }
