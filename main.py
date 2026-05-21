import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.config import get_pipeline_config, get_sources_config
from scrapers.compliments.scraper import ComplimentsScraper
from pipelines.ingestion.run import run_ingestion_pipeline
from storage.duckdb.store import DuckDBStore
from storage.huggingface.upload import HuggingFaceUploader

logger = setup_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="Reference DB Scraping Pipeline")
    parser.add_argument("--source", default="compliments", help="Source to scrape")
    parser.add_argument("--max-products", type=int, default=300, help="Max products to scrape")
    parser.add_argument("--upload-hf", action="store_true", help="Upload to Hugging Face")
    parser.add_argument("--save-only", action="store_true", help="Only save raw JSON, skip DB")
    return parser.parse_args()


def run_compliments_pipeline(max_products: int, upload_hf: bool = False, save_only: bool = False):
    logger.info("Starting Compliments scraping pipeline...")

    scraper = ComplimentsScraper()
    products = scraper.scrape(max_products=max_products)
    scraper.close()

    if not products:
        logger.error("No products scraped")
        return

    logger.info(f"Scraped {len(products)} products")

    pipeline_result = run_ingestion_pipeline(products)
    logger.info(f"Ingestion complete: {pipeline_result}")

    if not save_only:
        store = DuckDBStore()
        store.init_schemas()
        store.insert_raw_products(products)
        logger.info(f"Stored {len(products)} products in DuckDB")
        store.close()

    if upload_hf:
        uploader = HuggingFaceUploader()
        url = uploader.upload(products)
        logger.info(f"Uploaded to Hugging Face: {url}")

    logger.info("Pipeline completed successfully!")


def main():
    args = parse_args()

    if args.source == "compliments":
        run_compliments_pipeline(
            max_products=args.max_products,
            upload_hf=args.upload_hf,
            save_only=args.save_only,
        )
    else:
        logger.error(f"Unknown source: {args.source}")


if __name__ == "__main__":
    main()
