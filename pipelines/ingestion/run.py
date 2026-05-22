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


@dlt.source
def nutrition_source(nutrition_records: list[dict[str, Any]], products: list[dict[str, Any]]):
    product_map = {p.get("retailer_product_id"): p.get("product_id") for p in products}

    @dlt.resource(name="nutritional_info", write_disposition="replace", primary_key="retailer_product_id")
    def nutrition_resource():
        for record in nutrition_records:
            rid = record.get("retailer_product_id")
            record["product_id"] = product_map.get(rid)
            yield record

    return [nutrition_resource]


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


def run_nutrition_pipeline(nutrition_records: list[dict[str, Any]], products: list[dict[str, Any]], pipeline_name: str = "nutrition_pipeline") -> dict[str, Any]:
    from utils.io_utils import save_raw_json
    save_raw_json(nutrition_records, "nutrition")
    logger.info(f"Saved {len(nutrition_records)} nutrition records to data/raw/")

    source = nutrition_source(nutrition_records, products)

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
        "nutrition_count": len(nutrition_records),
        "info": str(info),
    }
