import json, re, time, concurrent.futures
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scrapers.base import BaseScraper
from utils.logger import setup_logger


class SobeysScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__("sobeys", config)
        self.logger = setup_logger("scraper.sobeys")
        self.slug_path = Path("data/slug_by_rid.json")

    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        skip_existing = kwargs.get("skip_existing", True)
        return self._scrape_all(skip_existing=skip_existing)

    def _scrape_all(self, skip_existing: bool = True) -> list[dict[str, Any]]:
        if not self.slug_path.exists():
            self.logger.error("slug_by_rid.json not found. Run the Voila scraper first.")
            return []

        with open(self.slug_path) as f:
            slug_by_rid = json.load(f)

        all_slugs = list(slug_by_rid.values())
        products = []
        seen = set()

        products_path = Path("data/sobeys_products.json")
        if skip_existing and products_path.exists():
            with open(products_path) as f:
                for p in json.load(f):
                    products.append(p)
                    slug = p.get("sobeys_url", "").split("/")[-1]
                    seen.add(slug)

        remaining = [s for s in all_slugs if s not in seen]
        if not remaining:
            self.logger.info(f"All {len(products)} products already scraped")
            return products

        self.logger.info(f"Total slugs: {len(all_slugs)}, done: {len(seen)}, remaining: {len(remaining)}")
        results = self._scrape_slugs(remaining, products)
        return results

    def _scrape_slugs(self, slugs: list[str], existing: list | None = None) -> list[dict[str, Any]]:
        products = existing or []
        product_map = {p.get("sobeys_url", "").split("/")[-1]: p for p in products}
        nutrition = []

        nutrition_path = Path("data/sobeys_nutrition.json")
        if nutrition_path.exists():
            with open(nutrition_path) as f:
                nutrition = json.load(f)
        nut_map = {n.get("sobeys_url", "").split("/")[-1]: n for n in nutrition}

        start = time.time()
        BATCH_SIZE = 200
        TOTAL = len(slugs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            for batch_start in range(0, TOTAL, BATCH_SIZE):
                batch = slugs[batch_start:batch_start + BATCH_SIZE]
                futures = {executor.submit(self._process, slug): slug for slug in batch}
                batch_count = 0
                for future in concurrent.futures.as_completed(futures):
                    slug = futures[future]
                    r = future.result()
                    if r:
                        prod, nut = r
                        product_map[slug] = prod
                        nut_map[slug] = nut
                        batch_count += 1

                elapsed = time.time() - start
                done = batch_start + len(batch)
                rate = done / elapsed if elapsed > 0 else 0
                remaining_eta = (TOTAL - done) / rate if rate > 0 else 0
                self.logger.info(
                    f"Batch {batch_start//BATCH_SIZE + 1}/{(TOTAL+BATCH_SIZE-1)//BATCH_SIZE}: "
                    f"+{batch_count} ({len(product_map)} total, {done}/{TOTAL}, "
                    f"{elapsed:.0f}s, {rate:.0f}/s, ETA: {remaining_eta:.0f}s)"
                )

                with open(Path("data/sobeys_products.json"), "w") as f:
                    json.dump(list(product_map.values()), f, indent=2)
                with open(Path("data/sobeys_nutrition.json"), "w") as f:
                    json.dump(list(nut_map.values()), f, indent=2)

        total_time = time.time() - start
        self.logger.info(f"COMPLETE: {len(product_map)} products, {len(nut_map)} nutrition in {total_time:.0f}s")
        return list(product_map.values())

    def _process(self, slug: str):
        url = f"https://www.sobeys.com/products/{slug}"
        try:
            resp = self.client.get(url, timeout=10)
            if resp.status_code != 200 or "application/ld+json" not in resp.text:
                return None
            match = re.search(
                r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                resp.text, re.DOTALL
            )
            if not match:
                return None
            data = json.loads(match.group(1))
            if not isinstance(data, dict) or data.get("@type") != "Product":
                return None
            return self._parse(data, url)
        except Exception:
            return None

    def _parse(self, data: dict, url: str):
        n = data.get("nutrition", {})
        brand_raw = data.get("brand", {})
        brand = brand_raw.get("name") if isinstance(brand_raw, dict) else brand_raw
        img = data.get("image")
        image = img[0] if isinstance(img, list) else img

        prod = {
            "sobeys_url": url,
            "sku": data.get("sku"),
            "brand": brand,
            "product_name": data.get("name"),
            "description": data.get("description", ""),
            "image_url": image,
            "price": data.get("offers", {}).get("price"),
            "price_currency": data.get("offers", {}).get("priceCurrency"),
            "availability": data.get("offers", {}).get("availability"),
            "source": "sobeys",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        def pv(v):
            if not v:
                return None
            m = re.search(r"(\d+\.?\d*)", str(v))
            return float(m.group(1)) if m else None

        nut = {
            "product_id": data.get("sku"),
            "sobeys_url": url,
            "serving_size": n.get("servingSize"),
            "calories": pv(n.get("calories")),
            "fat_g": pv(n.get("fatContent")),
            "saturated_fat_g": pv(n.get("saturatedFatContent")),
            "trans_fat_g": pv(n.get("transFatContent")),
            "cholesterol_mg": pv(n.get("cholesterolContent")),
            "sodium_mg": pv(n.get("sodiumContent")),
            "potassium_mg": pv(n.get("potassiumContent")),
            "carbohydrate_g": pv(n.get("carbohydrateContent")),
            "fibre_g": pv(n.get("fiberContent")),
            "sugars_g": pv(n.get("sugarContent")),
            "protein_g": pv(n.get("proteinContent")),
            "calcium_mg": pv(n.get("calciumContent")),
            "iron_mg": pv(n.get("ironContent")),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        return prod, nut
