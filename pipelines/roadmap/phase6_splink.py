import json
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase6")


def run(core_variant: dict) -> dict:
    logger.info("=" * 60)
    logger.info("PHASE 6: Entity Resolution (deterministic matching)")
    logger.info("=" * 60)

    canonical = core_variant.get("canonical_products", [])
    variants = core_variant.get("product_variants", [])

    core_key_map = {}
    for c in canonical:
        ck = c.get("core_key", "")
        core_key_map[ck] = c["canonical_id"]

    matches = []
    clusters = {}

    for v in variants:
        ck = None
        for c in canonical:
            if c["canonical_id"] == v.get("canonical_id"):
                ck = c.get("core_key")
                break
        if ck not in clusters:
            clusters[ck] = []
        clusters[ck].append(v)

    match_pairs = []
    ck_to_cid = {}
    for c in canonical:
        ck_to_cid[c.get("core_key", "")] = c["canonical_id"]

    seen_pairs = set()
    for i, v1 in enumerate(variants):
        for j, v2 in enumerate(variants):
            if i >= j:
                continue
            cid1 = v1.get("canonical_id")
            cid2 = v2.get("canonical_id")
            if cid1 == cid2:
                continue

            pair_key = tuple(sorted([cid1, cid2]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            name1 = v1.get("product_type", "")
            name2 = v2.get("product_type", "")
            if name1 and name2 and (name1.lower() == name2.lower() or
                                     name1.lower().startswith(name2.lower()) or
                                     name2.lower().startswith(name1.lower())):
                match_pairs.append({
                    "canonical_a": cid1,
                    "canonical_b": cid2,
                    "variant_a": v1.get("variant_id"),
                    "variant_b": v2.get("variant_id"),
                    "product_type_a": name1,
                    "product_type_b": name2,
                    "match_type": "deterministic_name",
                    "probability": 0.9,
                })

    logger.info(f"  Canonical clusters: {len(clusters)}")
    logger.info(f"  Cross-canonical name matches: {len(match_pairs)}")

    variants_linked = sum(1 for v in variants if v.get("canonical_id"))
    logger.info(f"  Variants linked to canonical: {variants_linked}/{len(variants)}")

    result = {
        "clusters": {k: len(v) for k, v in clusters.items()},
        "match_pairs": match_pairs,
        "total_clusters": len(clusters),
        "total_variants": len(variants),
    }

    save_dir = Path("data/entity_resolution")
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "splink_matches.json", "w") as f:
        json.dump(result, f, indent=2)

    logger.info("=" * 60)
    logger.info("PHASE 6 COMPLETE")
    logger.info("=" * 60)
    return result
