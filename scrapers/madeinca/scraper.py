import json
from pathlib import Path
from typing import Any

from scrapers.base import BaseScraper
from utils.logger import setup_logger


class MadeInCanadaScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__("madeinca", config)
        self.logger = setup_logger("scraper.madeinca")
        self.url = "https://madeinca.ca/grocery-store-guide/"

    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        self.logger.info(f"Fetching {self.url}")
        resp = self._fetch(self.url)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "lxml")

        content = soup.find("div", class_="entry-content") or soup.find("article") or soup.body
        if not content:
            content = soup

        current_section = ""
        current_category = ""
        records = []

        for el in content.find_all(["h2", "h3", "table"]):
            if el.name == "h2":
                current_section = el.get_text(strip=True)
            elif el.name == "h3":
                current_category = el.get_text(strip=True)
            elif el.name == "table":
                rows = el.find_all("tr")
                if not rows:
                    continue
                headers = [h.get_text(strip=True).lower() for h in rows[0].find_all(["th", "td"])]
                if not any("brand" in h for h in headers):
                    continue
                for row in rows[1:]:
                    cols = row.find_all(["td", "th"])
                    if len(cols) >= 3:
                        brand = cols[0].get_text(strip=True)
                        products = cols[1].get_text(strip=True)
                        location = cols[2].get_text(strip=True)
                        if brand and products:
                            records.append({
                                "brand": brand,
                                "products": products,
                                "manufactured_in": location,
                                "category": current_category,
                                "section": current_section,
                            })

        self.logger.info(f"Scraped {len(records)} brands from {self.url}")
        return records

    def scrape_and_save(self):
        records = self.scrape()
        path = Path("data/raw_madeinca_brands.json")
        with open(path, "w") as f:
            json.dump(records, f, indent=2)
        self.logger.info(f"Saved {len(records)} records to {path}")
        return records
