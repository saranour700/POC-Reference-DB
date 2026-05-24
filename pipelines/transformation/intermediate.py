import re
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("pipeline.intermediate")

UNIT_ALIASES = {
    "ml": "ml", "milliliter": "ml", "millilitre": "ml", "milliliters": "ml",
    "l": "ml", "liter": "ml", "litre": "ml", "liters": "ml", "litres": "ml",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "g", "kilogram": "g", "kilograms": "g",
    "oz": "g", "ounce": "g", "ounces": "g",
    "lb": "g", "pound": "g", "pounds": "g",
    "count": "count", "pack": "count", "pk": "count",
    "ea": "count", "each": "count",
}

def normalize_quantity(text: str) -> dict:
    if not text:
        return {"quantity_raw": None, "quantity_unit": None, "pack_count": None, "pack_unit": None}
    text = text.strip().lower()

    pack_match = re.search(r'(\d+)\s*x\s*(\d+\.?\d*)\s*(ml|l|g|kg|oz|lb|count|pack|ea|each)?', text)
    if pack_match:
        pack_count = int(pack_match.group(1))
        item_qty = float(pack_match.group(2))
        unit = pack_match.group(3) or "g"
        normalized_unit = UNIT_ALIASES.get(unit, unit)
        return {
            "quantity_raw": item_qty * pack_count,
            "quantity_unit": normalized_unit,
            "pack_count": pack_count,
            "pack_unit": normalized_unit,
        }

    simple = re.search(r'(\d+\.?\d*)\s*(ml|l|g|kg|oz|lb|count|pack|ea|each|ounce|pound|gram|liter|litre|milliliter|millilitre)s?\.?\s*$', text)
    if simple:
        qty = float(simple.group(1))
        unit = simple.group(2)
        normalized_unit = UNIT_ALIASES.get(unit, unit)
        pack_count = None
        if normalized_unit == "count":
            pack_count = int(qty)
        return {
            "quantity_raw": qty,
            "quantity_unit": normalized_unit,
            "pack_count": pack_count,
            "pack_unit": normalized_unit if normalized_unit != "count" else None,
        }

    just_num = re.search(r'(\d+)', text)
    if just_num:
        return {"quantity_raw": float(just_num.group(1)), "quantity_unit": None, "pack_count": int(just_num.group(1)), "pack_unit": None}

    return {"quantity_raw": None, "quantity_unit": None, "pack_count": None, "pack_unit": None}


def normalize_unit(value: float | None, unit: str | None) -> float | None:
    if value is None:
        return None
    if unit == "kg":
        return value * 1000
    if unit == "l":
        return value * 1000
    if unit in ("oz",):
        return round(value * 28.3495, 2)
    if unit in ("lb",):
        return round(value * 453.592, 2)
    return value


def parse_product_name(name: str) -> dict:
    if not name:
        return {"product_type": None, "variant": None, "size_text": None}

    cleaned = re.sub(r'\s+', ' ', name.strip())

    known_suffixes = r"(organic|balance|naturally\s+simple|free\s+from)"
    brand_match = re.match(r'^(compliments(?:\s+(?:' + known_suffixes + r'))?)', cleaned, re.I)
    brand_part = brand_match.group(1) if brand_match else "Compliments"
    after_brand = cleaned[len(brand_part):].strip()

    size_re = re.compile(
        r'\s+(\d[\d\s]*x\s*)?[\d.]+\s*(ml|milliliter|millilitre|l|liter|litre|'
        r'g|gram|kg|kilogram|oz|ounce|lb|pound|count|pack|ea|each)'
        r'(?:s|es|\.)?\s*$', re.I
    )
    size_match = size_re.search(after_brand)
    full_size = size_match.group(0) if size_match else ""

    core = after_brand[:len(after_brand) - len(full_size)].strip() if full_size else after_brand

    type_keywords = [
        "bacon", "cheese", "yogurt", "milk", "cream", "butter", "bread", "muffin", "chicken",
        "beef", "pork", "salmon", "tuna", "rice", "pasta", "sauce", "soup", "juice", "water",
        "chips", "cookies", "cake", "pie", "pizza", "eggs", "oil", "vinegar", "syrup", "honey",
        "jam", "peanut", "almond", "cashew", "walnut", "beans", "corn", "peas", "carrots",
        "broccoli", "spinach", "lettuce", "tomato", "onion", "potato", "apple", "banana",
        "orange", "grape", "strawberry", "blueberry", "raspberry", "ice cream", "frozen",
        "cereal", "oatmeal", "granola", "crackers", "nuts", "seeds", "chocolate", "candy",
        "gum", "mints", "coffee", "tea", "soda", "pop", "mayonnaise", "ketchup", "mustard",
        "pickle", "olive", "hummus", "dip", "salsa", "guacamole", "pancake", "waffle", "bagel",
        "croissant", "danish", "cookie", "brownie", "bars", "popcorn", "pretzels",
        "salad dressing", "vinegar", "soy sauce", "hot sauce", "barbecue sauce", "honey",
        "maple syrup", "sugar", "flour", "yeast", "gelatin", "pudding", "cake mix",
        "pizza dough", "pie crust", "tortilla", "pita", "naan", "flatbread",
        "rye bread", "pumpernickel", "sourdough", "whole wheat", "white bread",
        "eggs", "olive oil", "canola oil", "vegetable oil", "coconut oil",
        "frozen chicken", "frozen fish", "frozen vegetables", "frozen fruit",
        "canned beans", "canned tomatoes", "canned soup", "canned tuna",
        "ground beef", "chicken breast", "pork chops", "beef steak",
        "green beans", "black beans", "kidney beans", "chickpeas", "lentils",
    ]

    product_type = None
    variant = None

    if core:
        parts = core.split(" - ")
        if len(parts) > 1:
            product_type = parts[0].strip()
            variant = " - ".join(parts[1:]).strip()
        else:
            for tkw in type_keywords:
                if tkw in core.lower():
                    idx = core.lower().index(tkw)
                    end = idx + len(tkw)
                    product_type = core[idx:end].strip().title()
                    rest = core[end:].strip().title()
                    variant = rest if rest else None
                    break
            if not product_type:
                product_type = core if len(core) > 2 else None

    return {
        "product_type": product_type or None,
        "variant": variant or None,
        "size_text": full_size.strip() or None,
    }


def normalize_voila_product(p: dict) -> dict:
    parsed = parse_product_name(p.get("product_name"))
    qty = normalize_quantity(parsed.get("size_text") or p.get("size") or "")
    return {
        "product_id": p.get("product_id"),
        "source": "voila",
        "brand": p.get("brand", "Compliments"),
        "product_name": p.get("product_name"),
        "product_type": parsed["product_type"],
        "variant": parsed["variant"],
        "quantity": qty["quantity_raw"],
        "quantity_unit": qty["quantity_unit"],
        "price_cad": p.get("price_cad"),
        "image_url": p.get("image_url"),
        "category": p.get("category"),
        "is_available": p.get("is_available", True),
        "scraped_at": p.get("scraped_at"),
        "raw_size": parsed["size_text"] or p.get("size"),
        "pack_count": qty["pack_count"],
    }


def normalize_sobeys_product(p: dict) -> dict:
    parsed = parse_product_name(p.get("product_name"))
    qty = normalize_quantity(parsed.get("size_text") or "")
    return {
        "product_id": p.get("sku"),
        "source": "sobeys",
        "brand": p.get("brand", "Compliments"),
        "product_name": p.get("product_name"),
        "product_type": parsed["product_type"],
        "variant": parsed["variant"],
        "quantity": qty["quantity_raw"],
        "quantity_unit": qty["quantity_unit"],
        "price_cad": float(p["price"]) if p.get("price") else None,
        "image_url": p.get("image_url"),
        "category": None,
        "is_available": "InStock" in (p.get("availability") or ""),
        "scraped_at": p.get("scraped_at"),
        "raw_size": parsed["size_text"],
        "pack_count": qty["pack_count"],
    }


def merge_nutrition(voila_nut: list[dict], sobeys_nut: list[dict]) -> list[dict]:
    merged = []
    for n in voila_nut:
        merged.append({
            "product_id": n.get("product_id") or n.get("retailer_product_id"),
            "source": "voila",
            "serving_size": n.get("serving_size"),
            "calories": n.get("calories"),
            "fat_g": n.get("fat_g"),
            "saturated_fat_g": n.get("saturated_fat_g"),
            "trans_fat_g": n.get("trans_fat_g"),
            "polyunsaturated_fat_g": n.get("polyunsaturated_fat_g"),
            "monounsaturated_fat_g": n.get("monounsaturated_fat_g"),
            "omega6_g": n.get("omega6_g"),
            "omega3_g": n.get("omega3_g"),
            "carbohydrate_g": n.get("carbohydrate_g"),
            "fibre_g": n.get("fibre_g"),
            "sugars_g": n.get("sugars_g"),
            "sugar_alcohols_g": n.get("sugar_alcohols_g"),
            "protein_g": n.get("protein_g"),
            "cholesterol_mg": n.get("cholesterol_mg"),
            "sodium_mg": n.get("sodium_mg"),
            "potassium_mg": n.get("potassium_mg"),
            "calcium_mg": n.get("calcium_mg"),
            "iron_mg": n.get("iron_mg"),
            "scraped_at": n.get("scraped_at"),
        })
    for n in sobeys_nut:
        merged.append({
            "product_id": n.get("product_id"),
            "source": "sobeys",
            "serving_size": n.get("serving_size"),
            "calories": n.get("calories"),
            "fat_g": n.get("fat_g"),
            "saturated_fat_g": n.get("saturated_fat_g"),
            "trans_fat_g": n.get("trans_fat_g"),
            "polyunsaturated_fat_g": n.get("polyunsaturated_fat_g"),
            "monounsaturated_fat_g": n.get("monounsaturated_fat_g"),
            "omega6_g": n.get("omega6_g"),
            "omega3_g": n.get("omega3_g"),
            "carbohydrate_g": n.get("carbohydrate_g"),
            "fibre_g": n.get("fibre_g"),
            "sugars_g": n.get("sugars_g"),
            "sugar_alcohols_g": n.get("sugar_alcohols_g"),
            "protein_g": n.get("protein_g"),
            "cholesterol_mg": n.get("cholesterol_mg"),
            "sodium_mg": n.get("sodium_mg"),
            "potassium_mg": n.get("potassium_mg"),
            "calcium_mg": n.get("calcium_mg"),
            "iron_mg": n.get("iron_mg"),
            "scraped_at": n.get("scraped_at"),
        })
    logger.info(f"Merged {len(voila_nut)} Voila + {len(sobeys_nut)} Sobeys = {len(merged)} nutrition records")
    return merged


def run(staging: dict) -> dict:
    voila_products = [normalize_voila_product(p) for p in staging.get("stg_compliments_products", [])]
    sobeys_products = [normalize_sobeys_product(p) for p in staging.get("stg_sobeys_products", [])]
    nutrition = merge_nutrition(
        staging.get("stg_nutrition_voila", []),
        staging.get("stg_nutrition_sobeys", []),
    )

    logger.info(f"Intermediate: {len(voila_products)} Voila + {len(sobeys_products)} Sobeys products")
    return {
        "int_products": voila_products + sobeys_products,
        "int_voila_products": voila_products,
        "int_sobeys_products": sobeys_products,
        "int_nutrition": nutrition,
    }
