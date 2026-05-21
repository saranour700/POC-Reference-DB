from pathlib import Path
import yaml
from dotenv import load_dotenv
import os

load_dotenv()


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_pipeline_config() -> dict:
    return load_yaml("configs/pipeline.yaml")


def get_sources_config() -> dict:
    return load_yaml("configs/sources.yaml")


def get_huggingface_token() -> str | None:
    return os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")


def get_huggingface_repo() -> str:
    return os.getenv("HF_REPO_ID", "saranour/compliments-products")
