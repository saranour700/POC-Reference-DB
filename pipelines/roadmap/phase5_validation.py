import json
from pathlib import Path
from collections import Counter
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase5")

VALID_UNITS = {"ml", "g", "count"}
VALID_SOURCES = {"voila", "sobeys"}
REQUIRED_CORE_FIELDS = ["canonical_id", "brand", "product_type"]
REQUIRED_VARIANT_FIELDS = ["variant_id", "canonical_id", "product_id", "source"]


def run(core_variant: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 5: Validation & Data Quality")
    logger.info("=" * 60)

    canonical = core_variant.get("canonical_products", [])
    variants = core_variant.get("product_variants", [])

    checks = []

    # Canoical checks
    for field in REQUIRED_CORE_FIELDS:
        missing = sum(1 for c in canonical if not c.get(field))
        rate = f"{missing}/{len(canonical)}" if canonical else "N/A"
        status = "PASS" if missing == 0 else "FAIL" if missing > len(canonical) * 0.1 else "WARN"
        checks.append({"layer": "canonical", "check": f"null_{field}", "status": status, "missing": rate})
        logger.info(f"  {'✅' if status=='PASS' else '⚠️'} canonical {field}: {rate} missing")

    no_type = sum(1 for c in canonical if not c.get("product_type"))
    checks.append({"layer": "canonical", "check": "product_type_missing", "status": "WARN" if no_type > 0 else "PASS", "count": no_type})

    # Variant checks
    for field in REQUIRED_VARIANT_FIELDS:
        missing = sum(1 for v in variants if not v.get(field))
        rate = f"{missing}/{len(variants)}" if variants else "N/A"
        status = "PASS" if missing == 0 else "FAIL" if missing > len(variants) * 0.05 else "WARN"
        checks.append({"layer": "variants", "check": f"null_{field}", "status": status, "missing": rate})
        logger.info(f"  {'✅' if status=='PASS' else '⚠️'} variants {field}: {rate} missing")

    # Quantity > 0
    zero_qty = sum(1 for v in variants if v.get("quantity") is not None and v["quantity"] <= 0)
    checks.append({"layer": "variants", "check": "quantity_zero_or_negative", "status": "FAIL" if zero_qty > 0 else "PASS", "count": zero_qty})
    if zero_qty > 0:
        logger.info(f"  ❌ variants: {zero_qty} with invalid quantity")

    # Unit check
    units = Counter(v.get("unit") for v in variants if v.get("unit"))
    invalid_units = {u for u in units if u and u not in VALID_UNITS}
    checks.append({"layer": "variants", "check": "invalid_units", "status": "WARN" if invalid_units else "PASS", "invalid": list(invalid_units)[:10]})
    if invalid_units:
        logger.info(f"  ⚠️ variants: invalid units {invalid_units}")

    # Source validity
    sources = set(v.get("source") for v in variants if v.get("source"))
    bad_sources = sources - VALID_SOURCES
    checks.append({"layer": "variants", "check": "unknown_sources", "status": "WARN" if bad_sources else "PASS", "unknown_sources": list(bad_sources)})

    # Duplicate variant_ids
    vids = [v["variant_id"] for v in variants if v.get("variant_id")]
    dup_vids = len(vids) - len(set(vids))
    checks.append({"layer": "variants", "check": "duplicate_variant_ids", "status": "FAIL" if dup_vids > 0 else "PASS", "count": dup_vids})

    # Orphan variants (no canonical)
    cids = set(c["canonical_id"] for c in canonical)
    orphan = sum(1 for v in variants if v.get("canonical_id") not in cids)
    checks.append({"layer": "variants", "check": "orphan_variants", "status": "FAIL" if orphan > 0 else "PASS", "count": orphan})

    # Summary
    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    passes = sum(1 for c in checks if c["status"] == "PASS")

    report = {
        "canonical_count": len(canonical),
        "variant_count": len(variants),
        "checks": checks,
        "summary": {"pass": passes, "warn": warns, "fail": fails},
        "passed": fails == 0,
    }

    save_dir = Path("data/validation")
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "validation_report.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"  Summary: ✅ {passes}  ⚠️ {warns}  ❌ {fails}")
    logger.info("=" * 60)
    logger.info("PHASE 5 COMPLETE")
    logger.info("=" * 60)
    return report
