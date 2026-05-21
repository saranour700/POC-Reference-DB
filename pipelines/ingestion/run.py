import dlt
from typing import Any
from utils.logger import setup_logger
from utils.io_utils import save_raw_json


logger = setup_logger("pipeline.ingestion")


@dlt.source
def compliments_source(products: list[dict[str, Any]]):
    @dlt.resource(name="compliments_products", write_disposition="replace")
    def products_resource():
        yield from products

    return [products_resource]


def run_ingestion_pipeline(products: list[dict[str, Any]], pipeline_name: str = "compliments_pipeline") -> dict[str, Any]:
    save_raw_json(products, "compliments")
    logger.info(f"Saved {len(products)} raw products to data/raw/")

    source = compliments_source(products)

    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination="duckdb",
        dataset_name="compliments",
        progress="log",
    )

    info = pipeline.run(source)
    logger.info(f"Pipeline run info: {info}")

    return {
        "pipeline_name": pipeline_name,
        "products_count": len(products),
        "info": str(info),
    }
