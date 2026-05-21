import duckdb
from pathlib import Path
from typing import Any
from utils.logger import setup_logger
from schemas.raw_schema import RAW_CREATE_TABLE
from schemas.normalized_schema import NORMALIZED_CREATE_TABLE


class DuckDBStore:
    def __init__(self, db_path: str = "data/staged/products.duckdb"):
        self.db_path = db_path
        self.logger = setup_logger("storage.duckdb")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(db_path)

    def init_schemas(self):
        self.conn.execute(RAW_CREATE_TABLE.format(table="raw_products"))
        self.conn.execute(NORMALIZED_CREATE_TABLE.format(table="normalized_products"))
        self.logger.info("Database schemas initialized")

    def insert_raw_products(self, products: list[dict[str, Any]]):
        import pandas as pd
        df = pd.DataFrame(products)
        self.conn.register("df_view", df)
        self.conn.execute("INSERT INTO raw_products SELECT * FROM df_view")
        self.logger.info(f"Inserted {len(products)} raw products")

    def query(self, sql: str) -> list[Any]:
        return self.conn.execute(sql).fetchall()

    def to_dataframe(self, table: str = "normalized_products") -> "pd.DataFrame":
        import pandas as pd
        return self.conn.execute(f"SELECT * FROM {table}").fetchdf()

    def close(self):
        self.conn.close()
