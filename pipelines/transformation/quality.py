from typing import Any
from collections import Counter
from utils.logger import setup_logger

logger = setup_logger("pipeline.quality")


def validate_products(products: list[dict], name: str) -> dict:
    total = len(products)
    if total == 0:
        logger.warning(f"{name}: empty dataset, skipping validation")
        return {"name": name, "total": 0, "passed": False, "checks": []}

    checks = []

    # 1. Null checks for required fields
    required = ["product_id", "brand", "product_name", "source"]
    for field in required:
        missing = sum(1 for p in products if not p.get(field))
        status = "PASS" if missing == 0 else "WARN" if missing < total * 0.1 else "FAIL"
        checks.append({
            "check": f"null_{field}",
            "status": status,
            "missing": missing,
            "total": total,
            "rate": f"{missing/total*100:.1f}%",
        })

    # 2. Price validity
    with_price = sum(1 for p in products if p.get("price_cad") is not None)
    zero_price = sum(1 for p in products if p.get("price_cad") is not None and float(p["price_cad"]) == 0)
    negative_price = sum(1 for p in products if p.get("price_cad") is not None and float(p["price_cad"]) < 0)
    checks.append({"check": "price_present", "status": "PASS" if with_price > total * 0.8 else "WARN",
                    "with_price": with_price, "total": total, "rate": f"{with_price/total*100:.1f}%"})
    if zero_price > 0:
        checks.append({"check": "zero_price", "status": "WARN", "count": zero_price, "total": total})
    if negative_price > 0:
        checks.append({"check": "negative_price", "status": "FAIL", "count": negative_price, "total": total})

    # 3. Name length
    short_names = sum(1 for p in products if p.get("product_name") and len(p["product_name"]) < 10)
    if short_names > 0:
        checks.append({"check": "short_names", "status": "WARN", "count": short_names, "total": total})

    # 4. Product type parsing rate
    with_type = sum(1 for p in products if p.get("product_type"))
    checks.append({"check": "product_type_parsed", "status": "PASS" if with_type > total * 0.7 else "WARN",
                    "parsed": with_type, "total": total, "rate": f"{with_type/total*100:.1f}%"})

    # 5. Quantity parsing rate
    with_qty = sum(1 for p in products if p.get("quantity") is not None)
    checks.append({"check": "quantity_parsed", "status": "PASS" if with_qty > total * 0.7 else "WARN",
                    "parsed": with_qty, "total": total, "rate": f"{with_qty/total*100:.1f}%"})

    # 6. Duplicate IDs
    ids = [p.get("product_id") for p in products if p.get("product_id")]
    dup_ids = len(ids) - len(set(ids))
    checks.append({"check": "duplicate_ids", "status": "WARN" if dup_ids > 0 else "PASS",
                    "duplicates": dup_ids, "total": total})

    # 7. Brand consistency
    brands = Counter(p.get("brand", "") for p in products)
    if len(brands) > 1:
        checks.append({"check": "multiple_brands", "status": "PASS" if len(brands) < 3 else "WARN",
                        "brands": dict(brands.most_common(5))})

    # Summarize
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    passed = failed == 0
    logger.info(f"{name}: {passed}/{failed}/{warns} (PASS/FAIL/WARN)")

    return {"name": name, "total": total, "passed": passed, "checks": checks}


def validate_nutrition(records: list[dict], name: str) -> dict:
    total = len(records)
    if total == 0:
        return {"name": name, "total": 0, "passed": False, "checks": []}

    checks = []

    # Product ID linkage
    no_pid = sum(1 for r in records if not r.get("product_id"))
    checks.append({"check": "null_product_id", "status": "FAIL" if no_pid > 0 else "PASS",
                    "missing": no_pid, "total": total})

    # Calories coverage
    with_cals = sum(1 for r in records if r.get("calories") is not None)
    checks.append({"check": "calories_present", "status": "PASS" if with_cals > total * 0.6 else "WARN",
                    "with_calories": with_cals, "total": total, "rate": f"{with_cals/total*100:.1f}%"})

    # Core nutrients present (fat, sodium, carbs, protein)
    core = ["fat_g", "sodium_mg", "carbohydrate_g", "protein_g"]
    for field in core:
        present = sum(1 for r in records if r.get(field) is not None)
        rate = present / total * 100
        checks.append({"check": f"{field}_present", "status": "PASS" if rate > 50 else "WARN",
                        "present": present, "total": total, "rate": f"{rate:.1f}%"})

    failed = sum(1 for c in checks if c["status"] == "FAIL")
    logger.info(f"{name}: {len(checks)} checks, {failed} FAIL")

    return {"name": name, "total": total, "passed": failed == 0, "checks": checks}


def run(int_products: list[dict], int_nutrition: list[dict]) -> dict:
    voila = [p for p in int_products if p.get("source") == "voila"]
    sobeys = [p for p in int_products if p.get("source") == "sobeys"]

    results = {
        "products_voila": validate_products(voila, "voila_products"),
        "products_sobeys": validate_products(sobeys, "sobeys_products"),
        "products_all": validate_products(int_products, "all_products"),
        "nutrition": validate_nutrition(int_nutrition, "nutrition_combined"),
    }

    # Print summary
    logger.info("=" * 50)
    logger.info("QUALITY REPORT SUMMARY")
    logger.info("=" * 50)
    for name, report in results.items():
        status = "✅" if report.get("passed") else "⚠️"
        logger.info(f"  {status} {name}: {report.get('total', 0)} rows, {len(report.get('checks', []))} checks")
    return results
