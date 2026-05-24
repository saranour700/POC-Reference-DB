import json, sys
from pathlib import Path
from typing import Any

from utils.logger import setup_logger
from pipelines.transformation.staging import run as run_staging
from pipelines.transformation.intermediate import run as run_intermediate
from pipelines.transformation.marts import run as run_marts
from pipelines.transformation.dedup import (
    dedup_within_source,
    find_cross_source_duplicates,
    dedup_cross_source,
)
from pipelines.transformation.quality import run as run_quality

logger = setup_logger("pipeline.transformation")


def save_output(data: list | dict, name: str):
    path = Path(f"data/transformed/{name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved {name}: {len(data) if isinstance(data, list) else 'dict'} → {path}")


def run():
    logger.info("=" * 60)
    logger.info("TRANSFORMATION PIPELINE START")
    logger.info("=" * 60)

    # Phase 1: Load raw data
    logger.info("\n--- STAGING (raw load) ---")
    staging = run_staging()
    for name, data in staging.items():
        logger.info(f"  {name}: {len(data)} rows")

    # Phase 2: Normalize
    logger.info("\n--- INTERMEDIATE (normalize) ---")
    intermediate = run_intermediate(staging)
    int_products = intermediate["int_products"]
    int_nutrition = intermediate["int_nutrition"]

    # Phase 3: Validate
    logger.info("\n--- QUALITY ---")
    quality = run_quality(int_products, int_nutrition)

    # Phase 4: Deduplicate within source
    logger.info("\n--- DEDUP (within-source) ---")
    voila_products = intermediate["int_voila_products"]
    sobeys_products = intermediate["int_sobeys_products"]
    voila_deduped = dedup_within_source(voila_products, "voila")
    sobeys_deduped = dedup_within_source(sobeys_products, "sobeys")

    # Phase 5: Cross-source dedup
    logger.info("\n--- DEDUP (cross-source) ---")
    duplicates = find_cross_source_duplicates(voila_deduped, sobeys_deduped)
    all_deduped = dedup_cross_source(int_products, duplicates)

    logger.info(f"  Products after all dedup: {len(all_deduped)}")
    logger.info(f"  Cross-source pairs found: {len(duplicates.get('duplicate_pairs', []))}")

    # Phase 6: Build marts (using original products for canonical building)
    logger.info("\n--- MARTS (canonical + variants + sources) ---")
    sobeys_raw = staging.get("stg_sobeys_products", [])
    marts = run_marts(intermediate, sobeys_raw)

    # Phase 7: Enrich marts with dedup info
    if len(duplicates.get("duplicate_pairs", [])) > 0:
        voila_to_sobeys = duplicates.get("voila_to_sobeys", {})
        for src in marts.get("fct_product_sources", []):
            if src.get("product_id") in voila_to_sobeys:
                src["deduplicated_to"] = voila_to_sobeys[src["product_id"]]
                src["is_duplicate"] = True

    # Save all outputs
    logger.info("\n--- SAVING OUTPUTS ---")
    for name, data in staging.items():
        save_output(data, f"stg_{name}")
    for name, data in intermediate.items():
        save_output(data, f"int_{name}")
    for name, data in marts.items():
        save_output(data, name)
    save_output(quality, "quality_report")
    save_output(duplicates.get("duplicate_pairs", []), "duplicate_pairs")
    save_output(all_deduped, "all_products_deduped")

    cnt = len(all_deduped)
    logger.info("\n" + "=" * 60)
    logger.info(f"TRANSFORMATION COMPLETE: {cnt} unique products, {len(int_nutrition)} nutrition records")
    logger.info("=" * 60)

    return {
        "staging": staging,
        "intermediate": intermediate,
        "marts": marts,
        "quality": quality,
        "deduped_count": cnt,
    }


if __name__ == "__main__":
    run()
