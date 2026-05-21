import json
from pathlib import Path
from datetime import datetime


def save_raw_json(data: list[dict], source: str, base_dir: str = "data/raw") -> str:
    raw_dir = Path(base_dir) / source
    raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{source}_{timestamp}.json"
    filepath = raw_dir / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return str(filepath)


def save_staged_json(data: list[dict], source: str, base_dir: str = "data/staged") -> str:
    staged_dir = Path(base_dir) / source
    staged_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{source}_staged_{timestamp}.json"
    filepath = staged_dir / filename
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return str(filepath)
