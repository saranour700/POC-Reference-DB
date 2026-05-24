import json
from pathlib import Path
from collections import Counter
from typing import Any
from utils.logger import setup_logger

logger = setup_logger("roadmap.phase1")


def profile_dataset(data: list[dict], name: str) -> dict:
    total = len(data)
    if total == 0:
        return {"name": name, "total": 0, "fields": []}

    all_keys = set()
    for row in data:
        all_keys.update(row.keys())

    fields = []
    for key in sorted(all_keys):
        values = [row.get(key) for row in data]
        non_null = [v for v in values if v is not None and v != ""]
        null_count = total - len(non_null)
        missing_pct = round(null_count / total * 100, 1)

        types = set(type(v).__name__ for v in non_null)
        unique_vals = len(set(str(v) for v in non_null)) if non_null else 0

        sample_vals = []
        if non_null:
            counter = Counter(str(v) for v in non_null)
            sample_vals = [v for v, _ in counter.most_common(5)]

        field_profile = {
            "field": key,
            "type": ", ".join(sorted(types)) if types else "null",
            "total": total,
            "non_null": len(non_null),
            "missing": null_count,
            "missing_pct": missing_pct,
            "unique_values": unique_vals,
            "sample_values": sample_vals[:5],
        }
        fields.append(field_profile)

    return {"name": name, "total": total, "fields": fields, "field_count": len(fields)}


def generate_data_dictionary(profiles: list[dict]) -> list[dict]:
    seen = {}
    rows = []
    for p in profiles:
        for f in p.get("fields", []):
            key = f["field"]
            if key not in seen:
                seen[key] = {
                    "field": key,
                    "types": set(),
                    "sources": [],
                    "total_missing_pct": 0,
                    "source_count": 0,
                }
            seen[key]["types"].add(f["type"])
            seen[key]["sources"].append(p["name"])
            seen[key][f"missing_pct_{p['name']}"] = f["missing_pct"]

    for key, info in seen.items():
        info["types"] = ", ".join(sorted(info["types"]))
        info["source_count"] = len(info["sources"])
        info["sources"] = ", ".join(info["sources"])
        rows.append(info)

    return rows


def run():
    logger.info("=" * 60)
    logger.info("PHASE 1: Data Profiling & Schema Discovery")
    logger.info("=" * 60)

    raw_dir = Path("data/raw")
    if not raw_dir.exists():
        logger.error("data/raw/ not found. Run phase 0 first.")
        return {}

    profiles = []
    for fpath in sorted(raw_dir.glob("raw_*.json")):
        if fpath.name == "source_metadata.json":
            continue
        with open(fpath) as f:
            data = json.load(f)
        if isinstance(data, list):
            profile = profile_dataset(data, fpath.stem)
            profiles.append(profile)
            logger.info(f"  {fpath.stem}: {profile['total']} rows, {profile['field_count']} fields")

            for field in profile["fields"]:
                if field["missing_pct"] > 50:
                    logger.info(f"    ⚠️ {field['field']}: {field['missing_pct']}% missing")
        else:
            logger.info(f"  {fpath.stem}: dict ({len(data)} keys)")

    dictionary = generate_data_dictionary(profiles)

    report = {
        "profiles": profiles,
        "data_dictionary": dictionary,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }

    save_dir = Path("data/profiling")
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "profiling_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Saved profiling report → data/profiling/profiling_report.json")

    logger.info("=" * 60)
    logger.info("PHASE 1 COMPLETE")
    logger.info("=" * 60)
    return report
