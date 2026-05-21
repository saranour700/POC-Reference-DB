import pandas as pd
from typing import Any
from datasets import Dataset, DatasetDict
from utils.logger import setup_logger
from utils.config import get_huggingface_token, get_huggingface_repo


class HuggingFaceUploader:
    def __init__(self, repo_id: str | None = None, token: str | None = None):
        self.repo_id = repo_id or get_huggingface_repo()
        self.token = token or get_huggingface_token()
        self.logger = setup_logger("storage.huggingface")

    def upload(self, data: list[dict[str, Any]], split_name: str = "train"):
        df = pd.DataFrame(data)

        df = df.drop(columns=["raw_data"], errors="ignore")

        dataset = Dataset.from_pandas(df)
        dataset_dict = DatasetDict({split_name: dataset})

        dataset_dict.push_to_hub(self.repo_id, token=self.token)
        self.logger.info(f"Uploaded dataset to {self.repo_id} (split: {split_name})")

        return f"https://huggingface.co/datasets/{self.repo_id}"

    def upload_from_duckdb(self, db_path: str, table: str = "normalized_products", split_name: str = "train"):
        import duckdb
        conn = duckdb.connect(db_path)
        df = conn.execute(f"SELECT * FROM {table}").fetchdf()
        conn.close()

        return self.upload(df.to_dict("records"), split_name)
