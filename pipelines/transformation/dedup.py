import re
from typing import Any
from collections import defaultdict
from utils.logger import setup_logger

logger = setup_logger("pipeline.dedup")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n)
    return n.strip()


def dedup_within_source(products: list[dict], source: str) -> list[dict]:
    seen_keys = set()
    deduped = []
    for p in products:
        pid = p.get("product_id") or normalize_name(p.get("product_name", ""))
        if not pid or pid in seen_keys:
            continue
        seen_keys.add(pid)
        deduped.append(p)
    logger.info(f"{source}: {len(products)} → {len(deduped)} after within-source dedup")
    return deduped


def find_cross_source_duplicates(voila: list[dict], sobeys: list[dict]) -> dict:
    rid_to_sobeys = {}
    for p in sobeys:
        sku = p.get("product_id")
        if sku:
            rid_to_sobeys[sku] = p

    name_to_sobeys = {}
    for p in sobeys:
        nn = normalize_name(p.get("product_name", ""))
        if nn:
            name_to_sobeys[nn] = p

    duplicates = []
    for p in voila:
        pid = p.get("product_id")
        rid = p.get("retailer_product_id")
        m = re.search(r'(\d+)', str(rid)) if rid else None
        rid_num = m.group(1) if m else None

        # Match by numeric RID == Sobeys SKU
        if rid_num and rid_num in rid_to_sobeys:
            duplicates.append((p, rid_to_sobeys[rid_num], "RID/SKU"))
            continue

        # Match by normalized name
        nn = normalize_name(p.get("product_name", ""))
        if nn and nn in name_to_sobeys:
            duplicates.append((p, name_to_sobeys[nn], "name"))
            continue

    logger.info(f"Cross-source duplicates found: {len(duplicates)}")
    return {
        "duplicate_pairs": duplicates,
        "voila_to_sobeys": {(p.get("product_id") or rid_num): s.get("product_id") for p, s, _ in duplicates
                          for rid_num in [re.search(r'(\d+)', str(p.get("retailer_product_id",""))).group(1) if p.get("retailer_product_id") and re.search(r'(\d+)', str(p.get("retailer_product_id"))) else None]
                          if rid_num or p.get("product_id")},
    }


def dedup_cross_source(int_products: list[dict], duplicates: dict) -> list[dict]:
    voila_to_sobeys = duplicates.get("voila_to_sobeys", {})
    keep = []
    seen_product_ids = set()

    for p in int_products:
        pid = p.get("product_id")
        if not pid or pid in seen_product_ids:
            continue
        seen_product_ids.add(pid)

        # If this is a Voila product that has a Sobeys match, drop it (keep Sobeys)
        if pid in voila_to_sobeys:
            continue

        keep.append(p)

    logger.info(f"Cross-source dedup: {len(int_products)} → {len(keep)}")
    return keep
