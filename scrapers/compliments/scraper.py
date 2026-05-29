import re
import json
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
                if fetch_details and partial.get("retailer_product_id"):
                    detail = self.scrape_detail(
                        pid, "", partial["retailer_product_id"]
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

    def scrape_nutrition(self, retailer_product_id: str) -> dict[str, Any] | None:
        url = f"https://voila.ca/products/_/{retailer_product_id}"
        try:
            resp = self._fetch(url)
            if resp.status_code != 200:
                url = f"https://voila.ca/products/dummy/{retailer_product_id}"
                resp = self._fetch(url)
            return self._parse_nutrition(resp.text, retailer_product_id)
        except Exception as e:
            self.logger.warning(f"Failed to fetch nutrition for {retailer_product_id}: {e}")
        return None

    def scrape_all_nutrition(self, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nutrition_records = []
        for p in products:
            rid = p.get("retailer_product_id")
            if not rid:
                continue
            nutrition = self.scrape_nutrition(rid)
            if nutrition:
                nutrition_records.append(nutrition)
                self.logger.info(f"  Nutrition for {p.get('product_name', rid)}: {nutrition.get('calories')} cal")
        return nutrition_records

    def _parse_nutrition(self, html: str, retailer_product_id: str) -> dict[str, Any] | None:
        from scrapling.parser import Selector
        page = Selector(html)

        header = page.find(["h2", "h3", "h4"], re.compile(r"Nutrit", re.I))
        if not header:
            return None

        serving_size = ""
        section = header.parent
        if section:
            text_after = section.get_all_text()
            match = re.search(r"per\s+(.+?)(?:\s*<br|\s*</div|\s*<table)", text_after, re.I | re.DOTALL)
            if not match:
                next_sibling = header.next
                if next_sibling and isinstance(next_sibling, str):
                    serving_size = next_sibling.strip()
            else:
                serving_size = match.group(1).strip()

        # Find table after the nutrition header — search within parent section first
        section = header.parent
        table = section.find("table") if section else None
        if not table:
            table = page.find("table")
        if not table:
            return None

        result = {
            "product_id": None,
            "retailer_product_id": retailer_product_id,
            "serving_size": serving_size,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

        nutrient_map = {
            "calories": ("calories", None),
            "fat": ("fat_g", "fat_daily_pct"),
            "saturated": ("saturated_fat_g", "saturated_fat_daily_pct"),
            "trans": ("trans_fat_g", None),
            "polyunsaturated": ("polyunsaturated_fat_g", None),
            "monounsaturated": ("monounsaturated_fat_g", None),
            "omega6": ("omega6_g", None),
            "omega3": ("omega3_g", None),
            "carbohydrate": ("carbohydrate_g", "carbohydrate_daily_pct"),
            "fibre": ("fibre_g", "fibre_daily_pct"),
            "sugars": ("sugars_g", "sugars_daily_pct"),
            "sugaralcohols": ("sugar_alcohols_g", None),
            "protein": ("protein_g", None),
            "cholesterol": ("cholesterol_mg", None),
            "sodium": ("sodium_mg", "sodium_daily_pct"),
            "potassium": ("potassium_mg", "potassium_daily_pct"),
            "calcium": ("calcium_mg", "calcium_daily_pct"),
            "iron": ("iron_mg", "iron_daily_pct"),
        }

        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all(["td", "th"])
            if not cols:
                continue
            cell_text = cols[0].get_all_text().strip()

            key = None
            value = None
            pct = None

            for nutrient_name, (value_key, pct_key) in nutrient_map.items():
                if cell_text.lower().startswith(nutrient_name) or cell_text.lower().replace(" ", "").startswith(nutrient_name):
                    key = nutrient_name
                    value = self._extract_nutrient_value(cell_text, nutrient_name)
                    if len(cols) > 1:
                        pct_text = cols[1].get_all_text().strip()
                        pct = self._extract_percentage(pct_text)
                    break

            if key:
                v_key, p_key = nutrient_map[key]
                if v_key:
                    result[v_key] = value
                if p_key and pct is not None:
                    result[p_key] = pct

        return result

    def _extract_nutrient_value(self, text: str, nutrient_name: str) -> float | None:
        # Remove nutrient name prefix
        after = re.sub(r'^[\s\u2000-\u206F]*' + re.escape(nutrient_name) + r'[\s\u2000-\u206F]*', '', text, flags=re.IGNORECASE)
        # Extract number with optional decimal and unit
        match = re.search(r'(\d+\.?\d*)', after)
        if match:
            return float(match.group(1))
        return None

    def _extract_percentage(self, text: str) -> float | None:
        if not text:
            return None
        match = re.search(r'(\d+\.?\d*)\s*%', text)
        if match:
            return float(match.group(1))
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
