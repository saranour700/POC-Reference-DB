import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.logger import setup_logger
from utils.config import get_pipeline_config, get_sources_config
from scrapers.compliments.scraper import ComplimentsScraper
from scrapers.sobeys.scraper import SobeysScraper
from scrapers.alimentsduquebec.scraper import AlimentsDuQuebecScraper
from pipelines.ingestion.run import run_ingestion_pipeline
from storage.huggingface.upload import HuggingFaceUploader

logger = setup_logger("main")


def parse_args():
    parser = argparse.ArgumentParser(description="Reference DB Scraping Pipeline")
    parser.add_argument("--source", default="compliments", help="Source to scrape")
    parser.add_argument("--max-products", type=int, default=300, help="Max products to scrape")
    parser.add_argument("--upload-hf", action="store_true", help="Upload to Hugging Face")
    parser.add_argument("--nutrition", action="store_true", help="Scrape nutritional information")
    return parser.parse_args()


def run_compliments_pipeline(max_products: int, upload_hf: bool = False):
    logger.info("Starting Compliments scraping pipeline...")

    scraper = ComplimentsScraper()
    products = scraper.scrape(max_products=max_products, fetch_details=False)
    scraper.close()

    if not products:
        logger.error("No products scraped")
        return

    logger.info(f"Scraped {len(products)} products")

    pipeline_result = run_ingestion_pipeline(products)
    logger.info(f"Ingestion complete: {pipeline_result}")

    if upload_hf:
        uploader = HuggingFaceUploader()
        url = uploader.upload(products)
        logger.info(f"Uploaded to Hugging Face: {url}")

    logger.info("Pipeline completed successfully!")


def run_nutrition_pipeline(max_products: int = 300, upload_hf: bool = False):
    import json
    from pathlib import Path

    logger.info("Starting Nutrition scraping pipeline...")

    mapping_path = Path("data/products_for_nutrition.json")
    if mapping_path.exists():
        with open(mapping_path) as f:
            products = json.load(f)
        logger.info(f"Loaded {len(products)} products from mapping file")
    else:
        scraper = ComplimentsScraper()
        products = scraper.scrape(max_products=max_products, fetch_details=False)
        scraper.close()
        logger.info(f"Scraped {len(products)} products from category page")

    full_products = [p for p in products if p.get("rid") or p.get("retailer_product_id")]
    logger.info(f"Fetching nutrition for {len(full_products)} products...")

    scraper = ComplimentsScraper()
    nutrition_records = scraper.scrape_all_nutrition(full_products)
    scraper.close()

    if not nutrition_records:
        logger.warning("No nutrition data scraped")
        return

    logger.info(f"Scraped nutrition for {len(nutrition_records)} products")

    # Map product_id from products
    product_map = {}
    for p in full_products:
        rid = p.get("retailer_product_id") or p.get("rid")
        uid = p.get("product_id") or p.get("uuid")
        if rid:
            product_map[rid] = uid
    for rec in nutrition_records:
        rec["product_id"] = product_map.get(rec.get("retailer_product_id"))

    from pipelines.ingestion.run import run_nutrition_pipeline as run_nutri
    result = run_nutri(nutrition_records, products)
    logger.info(f"Nutrition ingestion complete: {result}")

    if upload_hf:
        uploader = HuggingFaceUploader(repo_id="saraNour/compliments-nutrition")
        url = uploader.upload(nutrition_records)
        logger.info(f"Uploaded nutrition to Hugging Face: {url}")

    logger.info("Nutrition pipeline completed successfully!")


def run_alimentsduquebec_pipeline(upload_hf: bool = False):
    logger.info("Starting Aliments du Québec scraping pipeline...")

    scraper = AlimentsDuQuebecScraper()
    products = scraper.scrape()
    scraper.close()

    if not products:
        logger.error("No products scraped")
        return

    logger.info(f"Scraped {len(products)} products")

    if upload_hf:
        uploader = HuggingFaceUploader(repo_id="saraNour/alimentsduquebec-products")
        url = uploader.upload(products)
        logger.info(f"Uploaded to Hugging Face: {url}")

    logger.info("Aliments du Québec pipeline completed successfully!")


def run_sobeys_pipeline(upload_hf: bool = False):
    logger.info("Starting Sobeys scraping pipeline...")

    scraper = SobeysScraper()
    products = scraper.scrape()
    scraper.close()

    if not products:
        logger.error("No products scraped")
        return

    logger.info(f"Scraped {len(products)} products")

    if upload_hf:
        uploader = HuggingFaceUploader(repo_id="saraNour/sobeys-compliments-products")
        url = uploader.upload(products)
        logger.info(f"Uploaded to Hugging Face: {url}")

    logger.info("Sobeys pipeline completed successfully!")


def main():
    args = parse_args()

    if args.source == "compliments":
        if args.nutrition:
            run_nutrition_pipeline(max_products=args.max_products, upload_hf=args.upload_hf)
        else:
            run_compliments_pipeline(
                max_products=args.max_products,
                upload_hf=args.upload_hf,
            )
    elif args.source == "sobeys":
        run_sobeys_pipeline(upload_hf=args.upload_hf)
    elif args.source == "alimentsduquebec":
        run_alimentsduquebec_pipeline(upload_hf=args.upload_hf)
    else:
        logger.error(f"Unknown source: {args.source}")


if __name__ == "__main__":
    main()
