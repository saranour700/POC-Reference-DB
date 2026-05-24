import json
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase8")


def build_search_index(unified: list[dict]) -> dict:
    index = {}
    for u in unified:
        name_parts = [
            u.get("brand", ""),
            u.get("product_type", ""),
            u.get("flavor", ""),
            u.get("formula", ""),
        ]
        search_text = " ".join(p for p in name_parts if p)

        tokens = search_text.lower().split()
        for token in tokens:
            if token not in index:
                index[token] = []
            if u["canonical_id"] not in [x["canonical_id"] for x in index[token]]:
                index[token].append({
                    "canonical_id": u["canonical_id"],
                    "product_type": u.get("product_type"),
                    "flavor": u.get("flavor"),
                    "variant_count": u.get("variant_count"),
                    "sources": u.get("sources"),
                })
    return index


def run(unified: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 8: Consumption Layer / Search API")
    logger.info("=" * 60)

    unified_products = unified.get("unified_products", [])
    logger.info(f"  Building search index for {len(unified_products)} products")

    search_index = build_search_index(unified_products)
    logger.info(f"  Search index tokens: {len(search_index)}")

    summary = {
        "total_canonical_products": len(unified_products),
        "total_tokens_in_search_index": len(search_index),
        "products_with_variants": sum(1 for u in unified_products if u["variant_count"] > 0),
        "products_with_multiple_sources": sum(1 for u in unified_products if u["source_count"] > 1),
        "brands": sorted(set(u.get("brand", "") for u in unified_products if u.get("brand"))),
        "product_types": sorted(set(u.get("product_type", "") for u in unified_products if u.get("product_type")))[:20],
    }

    save_dir = Path("data/consumption")
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(save_dir / "search_index.json", "w") as f:
        json.dump(search_index, f, indent=2)
    with open(save_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"  Saved → data/consumption/")
    logger.info(f"  Summary: {summary['total_canonical_products']} products, {summary['total_tokens_in_search_index']} search tokens")

    logger.info("=" * 60)
    logger.info("PHASE 8 COMPLETE")
    logger.info("=" * 60)

    return {"search_index": search_index, "summary": summary}
