import re, json
from pathlib import Path
from typing import Any
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase3")

FLAVOR_KEYWORDS = [
    "strawberry", "blueberry", "raspberry", "blackberry", "cherry", "grape",
    "apple", "banana", "orange", "lemon", "lime", "pineapple", "mango",
    "peach", "pear", "plum", "apricot", "coconut", "vanilla", "chocolate",
    "caramel", "coffee", "mocha", "cappuccino", "espresso", "matcha",
    "green tea", "chai", "cinnamon", "maple", "honey", "almond", "peanut",
    "hazelnut", "walnut", "pecan", "cashew", "pistachio", "mixed berry",
    "tropical fruit", "fruit punch", "cranberry", "pomegranate", "watermelon",
    "kiwi", "passion fruit", "guava", "lychee", "mango peach", "apple cinnamon",
    "lemonade", "orange mango", "berry", "mixed fruit", "sea salt",
    "salt and vinegar", "sour cream and onion", "barbecue", "bbq",
    "hickory", "smoked", "original", "plain", "unsweetened", "unsw",
    "extra virgin", "virgin",
]

FORMULA_KEYWORDS = [
    "low fat", "reduced fat", "fat free", "nonfat", "no fat",
    "low sodium", "reduced sodium", "no salt added", "unsalted",
    "low sugar", "no sugar added", "sugar free", "unsweetened",
    "low calorie", "light",
    "gluten free", "lactose free", "dairy free", "egg free", "nut free",
    "organic", "natural", "whole grain", "multigrain", "ancient grain",
    "with probiotic", "probiotic", "with fiber", "high fiber",
    "added calcium", "with vitamin", "fortified",
    "thick and creamy", "creamy", "smooth",
    "spicy", "hot", "mild", "medium", "extra hot",
]

PACKAGING_KEYWORDS = [
    "bottle", "can", "box", "bag", "pouch", "jar", "tub", "cup",
    "tray", "container", "packet", "sachet", "tin", "carton",
    "brick", "pkg", "package", "wrapped", "roll", "bar", "stick",
    "tube", "spray", "squeeze", "bottle", "decanter", "pitcher",
    "skin pack", "value pack", "family pack", "multi pack", "variety pack",
]

UNIT_ALIASES = {
    "ml": "ml", "milliliter": "ml", "millilitre": "ml", "milliliters": "ml",
    "l": "ml", "liter": "ml", "litre": "ml", "liters": "ml",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "g", "kilogram": "g", "kilograms": "g",
    "oz": "g", "ounce": "g", "ounces": "g",
    "lb": "g", "pound": "g", "pounds": "g",
    "count": "count", "pack": "count", "pk": "count", "ea": "count", "each": "count",
}


def extract_attributes(name: str | None) -> dict:
    if not name:
        return {
            "brand": None, "product_type": None, "flavor": None,
            "formula": None, "quantity_raw": None, "unit": None,
            "packaging": None, "count": None,
        }

    cleaned = re.sub(r'\s+', ' ', name.strip())

    brand_match = re.match(r'^(compliments(?:\s+(?:organic|balance|naturally\s+simple|free\s+from))?)', cleaned, re.I)
    brand = brand_match.group(1).strip() if brand_match else "Compliments"
    after_brand = cleaned[len(brand_match.group(1)):].strip() if brand_match else cleaned

    quantity_info = extract_quantity(after_brand)
    size_text = quantity_info.get("size_text", "")
    core = after_brand[:len(after_brand) - len(size_text)].strip() if size_text else after_brand

    formula = extract_formula(core)
    formula_text = formula.get("formula_text", "")
    if formula_text:
        core = core[:len(core) - len(formula_text)].strip() if formula_text in core else core

    flavor = extract_flavor(core)
    flavor_text = flavor.get("flavor_text", "")
    if flavor_text:
        core = core.replace(flavor_text, "", 1).strip()

    packaging = extract_packaging(core)
    packaging_text = packaging.get("packaging_text", "")
    if packaging_text:
        core = core.replace(packaging_text, "", 1).strip()

    product_type = core.strip().title() if core.strip() else None

    return {
        "brand": brand,
        "product_type": product_type,
        "flavor": flavor.get("flavor", None),
        "formula": formula.get("formula", None),
        "quantity_raw": quantity_info.get("quantity_num"),
        "unit": quantity_info.get("unit_normalized"),
        "packaging": packaging.get("packaging", None),
        "count": quantity_info.get("count"),
    }


def extract_quantity(text: str) -> dict:
    pack = re.search(r'(\d+)\s*x\s*(\d+\.?\d*)\s*(ml|l|g|kg|oz|lb|count|pack|ea|each)?', text, re.I)
    if pack:
        count = int(pack.group(1))
        qty = float(pack.group(2))
        unit = pack.group(3) or "g"
        size_text = pack.group(0)
        return {
            "quantity_num": qty * count if unit not in ("count", "pack", "ea", "each") else count,
            "unit_normalized": UNIT_ALIASES.get(unit.lower(), unit),
            "count": count,
            "size_text": size_text,
        }

    simple = re.search(r'(\d+\.?\d*)\s*(ml|l|g|kg|oz|lb|count|pack|ea|each)s?\.?\s*$', text, re.I)
    if simple:
        qty = float(simple.group(1))
        unit = simple.group(2).lower()
        return {
            "quantity_num": qty if unit not in ("count", "pack", "ea", "each") else qty,
            "unit_normalized": UNIT_ALIASES.get(unit, unit),
            "count": int(qty) if unit in ("count", "pack", "ea", "each") else None,
            "size_text": simple.group(0),
        }

    return {"quantity_num": None, "unit_normalized": None, "count": None, "size_text": None}


def extract_formula(text: str) -> dict:
    lower = text.lower()
    for kw in sorted(FORMULA_KEYWORDS, key=len, reverse=True):
        if kw in lower:
            idx = lower.index(kw)
            return {"formula": kw, "formula_text": text[idx:idx + len(kw)]}
    return {"formula": None, "formula_text": None}


def extract_flavor(text: str) -> dict:
    lower = text.lower()
    for kw in sorted(FLAVOR_KEYWORDS, key=len, reverse=True):
        if kw in lower:
            idx = lower.index(kw)
            return {"flavor": kw.title(), "flavor_text": text[idx:idx + len(kw)]}
    return {"flavor": None, "flavor_text": None}


def extract_packaging(text: str) -> dict:
    lower = text.lower()
    for kw in sorted(PACKAGING_KEYWORDS, key=len, reverse=True):
        pattern = r'\b' + re.escape(kw) + r'\b'
        m = re.search(pattern, lower)
        if m:
            return {"packaging": kw, "packaging_text": text[m.start():m.end()]}
    return {"packaging": None, "packaging_text": None}


def process_products(products: list[dict], source: str) -> list[dict]:
    out = []
    for p in products:
        name = p.get("product_name_raw") or p.get("product_name") or p.get("name")
        attrs = extract_attributes(name)
        out.append({
            "product_id": p.get("product_id") or p.get("sku") or p.get("uuid"),
            "source": source,
            "product_name_raw": name,
            **attrs,
        })
    logger.info(f"  {source}: {len(out)} products parsed ({sum(1 for x in out if x['product_type'])} with type)")
    return out


def run(normalized: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 3: Attribute Extraction")
    logger.info("=" * 60)

    voila = process_products(normalized.get("stg_compliments_products", []), "voila")
    sobeys = process_products(normalized.get("stg_sobeys_products", []), "sobeys")
    all_parsed = voila + sobeys

    with_type = sum(1 for p in all_parsed if p["product_type"])
    with_flavor = sum(1 for p in all_parsed if p["flavor"])
    with_qty = sum(1 for p in all_parsed if p["quantity_raw"])
    logger.info(f"  Attributes extracted: {with_type} type, {with_flavor} flavor, {with_qty} quantity")

    save_dir = Path("data/parsed")
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "parsed_products.json", "w") as f:
        json.dump(all_parsed, f, indent=2)

    for name, data in [("parsed_voila", voila), ("parsed_sobeys", sobeys)]:
        with open(save_dir / f"{name}.json", "w") as f:
            json.dump(data, f, indent=2)

    logger.info("=" * 60)
    logger.info("PHASE 3 COMPLETE")
    logger.info("=" * 60)
    return {"parsed_products": all_parsed, "parsed_voila": voila, "parsed_sobeys": sobeys}
