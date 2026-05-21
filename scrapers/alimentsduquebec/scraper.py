from scrapers.base import BaseScraper
from typing import Any


class AlimentsDuQuebecScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__("alimentsduquebec", config)

    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        self.logger.info("Aliments du Québec scraper not yet implemented")
        return []
