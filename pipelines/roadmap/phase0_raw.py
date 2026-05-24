import json, shutil
from pathlib import Path
from datetime import datetime, timezone
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase0")


def save_raw(data: list | dict, name: str):
    path = Path(f"data/raw/{name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved raw → {path} ({len(data) if isinstance(data, list) else 'dict'} records)")


def run():
    logger.info("=" * 60)
    logger.info("PHASE 0: Raw Data Collection (no cleaning, no assumptions)")
    logger.info("=" * 60)

    sources = {
        "raw_products_voila": "data/products_for_nutrition.json",
        "raw_products_sobeys": "data/sobeys_products.json",
        "raw_nutrition_voila": "data/nutrition_records.json",
        "raw_nutrition_sobeys": "data/sobeys_nutrition.json",
        "raw_rid_uuid_mapping": "data/rid_uuid_mapping.json",
        "raw_slug_by_rid": "data/slug_by_rid.json",
    }

    metadata = []
    for name, src_path in sources.items():
        p = Path(src_path)
        if not p.exists():
            logger.warning(f"Source not found: {src_path}")
            continue
        with open(p) as f:
            data = json.load(f)
        save_raw(data, name)

        row_count = len(data) if isinstance(data, list) else 1
        metadata.append({
            "source_name": name,
            "filename": f"{name}.json",
            "source_file": src_path,
            "record_count": row_count,
            "format": "json",
            "scraped_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })

    with open("data/raw/source_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    logger.info(f"Saved source metadata: {len(metadata)} sources")

    logger.info("=" * 60)
    logger.info("PHASE 0 COMPLETE")
    logger.info("=" * 60)
    return metadata
