import re
import json
import httpx
from datetime import datetime, timezone
from typing import Any

from scrapers.base import BaseScraper
from utils.logger import setup_logger


class ComplimentsScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__("compliments", config)
        self.logger = setup_logger("scraper.compliments")
        self.category_url = "https://voila.ca/categories?brands=Compliments"

    def scrape(self, max_products: int = 300, fetch_details: bool = True) -> list[dict[str, Any]]:
        products: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        self.logger.info("Fetching products from voila.ca...")
        resp = self._fetch(self.category_url)

        page_data = self._extract_initial_state(resp.text)
        if not page_data:
            self.logger.warning("No INITIAL_STATE found on page")
            return products

        entities = page_data["data"]["products"]["productEntities"]
        catalogue = page_data["data"]["products"]["catalogue"]["data"]
        all_uuids = catalogue["productGroups"][0]["products"]

        for pid in all_uuids:
            if len(products) >= max_products:
                break
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            if pid in entities:
                product = self._parse_entity(entities[pid])
                if product:
                    products.append(product)
            else:
                partial = self._make_partial_product(pid)
                if fetch_details and partial.get("retailer_product_id") and partial.get("slug"):
                    detail = self.scrape_detail(
                        pid, partial["slug"], partial["retailer_product_id"]
                    )
                    if detail:
                        partial.update(detail)
                products.append(partial)

        self.logger.info(f"Total products scraped: {len(products)} (full: {sum(1 for p in products if p.get('product_name') is not None)}, partial: {sum(1 for p in products if p.get('product_name') is None)})")
        return products

    def fetch_missing_details(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched = []
        for p in products:
            if p.get("product_name") is None:
                pid = p.get("product_id")
                rid = p.get("retailer_product_id")
                slug = p.get("slug")
                if pid and rid and slug:
                    detail = self.scrape_detail(pid, slug, rid)
                    if detail:
                        p.update(detail)
            enriched.append(p)
        return enriched

    def scrape_detail(self, pid: str, slug: str, retailer_product_id: str) -> dict[str, Any] | None:
        url = f"https://voila.ca/products/{slug}/{retailer_product_id}"
        try:
            resp = self._fetch(url)
            ld_products = self._extract_jsonld(resp.text)
            if ld_products:
                return ld_products[0]

            page_data = self._extract_initial_state(resp.text)
            if page_data:
                entities = page_data["data"]["products"]["productEntities"]
                if pid in entities:
                    return self._parse_entity(entities[pid])
        except Exception as e:
            self.logger.warning(f"Failed to fetch detail for {pid}: {e}")
        return None

    def scrape_all_from_html(self) -> list[dict[str, Any]]:
        resp = self._fetch(self.category_url)
        products = self._extract_initial_state(resp.text)
        if not products:
            return []

        entities = products["data"]["products"]["productEntities"]
        catalogue = products["data"]["products"]["catalogue"]["data"]
        uuids = catalogue["productGroups"][0]["products"]

        results = []
        seen = set()
        for pid in uuids:
            if pid in seen:
                continue
            seen.add(pid)
            if pid in entities:
                product = self._parse_entity(entities[pid])
                if product:
                    results.append(product)
            else:
                results.append(self._make_partial_product(pid))

        return results

    def _extract_initial_state(self, html: str) -> dict | None:
        marker = "window.__INITIAL_STATE__="
        idx = html.find(marker)
        if idx == -1:
            return None

        start = idx + len(marker)
        depth = 0
        end = start
        for i in range(start, len(html)):
            if html[i] == "{":
                depth += 1
            elif html[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        try:
            return json.loads(html[start:end])
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse INITIAL_STATE: {e}")
            return None

    def _extract_jsonld(self, html: str) -> list[dict] | None:
        scripts = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        products = []
        for script in scripts:
            try:
                data = json.loads(script)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    products.append(data)
            except json.JSONDecodeError:
                continue
        return products if products else None

    def _parse_entity(self, entity: dict) -> dict[str, Any] | None:
        try:
            raw_price = entity.get("price", {})
            image = entity.get("image", {})

            category_path = entity.get("categoryPath", [])
            if category_path and isinstance(category_path[-1], dict):
                category = category_path[-1].get("name", "")
            elif category_path and isinstance(category_path[-1], str):
                category = category_path[-1]
            else:
                category = ""

            size_info = entity.get("size", {})
            size_value = (
                size_info.get("value")
                if isinstance(size_info, dict)
                else str(size_info)
            ) or ""

            price_amount = None
            price_currency = "CAD"
            if isinstance(raw_price, dict):
                current = raw_price.get("current", {})
                if isinstance(current, dict):
                    price_amount = current.get("amount")
                    price_currency = current.get("currency", "CAD")

            return {
                "product_id": entity.get("productId"),
                "retailer_product_id": entity.get("retailerProductId"),
                "brand": entity.get("brand"),
                "product_name": entity.get("name"),
                "price_cad": float(price_amount) if price_amount else None,
                "price_currency": price_currency,
                "size": size_value,
                "image_url": image.get("src", "") if isinstance(image, dict) else "",
                "category": category,
                "is_available": entity.get("available", True),
                "source": self.source_name,
                "source_url": "https://voila.ca/categories?brands=Compliments",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "raw_data": entity,
            }
        except Exception as e:
            self.logger.warning(f"Failed to parse entity: {e}")
            return None

    def _make_partial_product(self, pid: str, slug: str | None = None, retailer_product_id: str | None = None) -> dict[str, Any]:
        return {
            "product_id": pid,
            "retailer_product_id": retailer_product_id,
            "slug": slug,
            "brand": "Compliments",
            "product_name": None,
            "price_cad": None,
            "price_currency": None,
            "size": None,
            "image_url": None,
            "category": None,
            "is_available": None,
            "source": self.source_name,
            "source_url": self.category_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "raw_data": None,
        }
