import json
from pathlib import Path
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase7")


def run(core_variant: dict, parsed: dict, nutrition: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 7: Unified Product Graph")
    logger.info("=" * 60)

    canonical = core_variant.get("canonical_products", [])
    variants = core_variant.get("product_variants", [])
    all_parsed = parsed.get("parsed_products", [])

    pid_to_variant = {}
    for v in variants:
        pid = v.get("product_id")
        if pid:
            pid_to_variant[pid] = v

    cid_to_canonical = {c["canonical_id"]: c for c in canonical}

    source_groups = defaultdict(list)
    for v in variants:
        cid = v.get("canonical_id")
        if cid:
            source_groups[cid].append(v.get("source", "unknown"))

    unified = []
    for c in canonical:
        cid = c["canonical_id"]
        linked_variants = [v for v in variants if v.get("canonical_id") == cid]
        sources = list(set(v.get("source", "") for v in linked_variants))
        unified.append({
            "canonical_id": cid,
            "brand": c.get("brand"),
            "product_type": c.get("product_type"),
            "flavor": c.get("flavor"),
            "formula": c.get("formula"),
            "variant_count": len(linked_variants),
            "sources": sources,
            "source_count": len(sources),
            "variants": [
                {
                    "variant_id": v["variant_id"],
                    "product_id": v["product_id"],
                    "source": v["source"],
                    "quantity": v.get("quantity"),
                    "unit": v.get("unit"),
                    "packaging": v.get("packaging"),
                    "count": v.get("count"),
                }
                for v in linked_variants
            ],
        })

    multi_source = sum(1 for u in unified if u["source_count"] > 1)
    logger.info(f"  Unified products: {len(unified)}")
    logger.info(f"  Multi-source products: {multi_source}")
    logger.info(f"  Avg variants/product: {len(variants)/max(len(unified),1):.1f}")

    save_dir = Path("data/unified")
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(save_dir / "unified_product_graph.json", "w") as f:
        json.dump(unified, f, indent=2)

    canonical_only = [{k: v for k, v in u.items() if k != "variants"} for u in unified]
    with open(save_dir / "unified_canonical_only.json", "w") as f:
        json.dump(canonical_only, f, indent=2)

    logger.info(f"  Saved → data/unified/")
    logger.info("=" * 60)
    logger.info("PHASE 7 COMPLETE")
    logger.info("=" * 60)
    return {"unified_products": unified}
