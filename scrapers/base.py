from abc import ABC, abstractmethod
from typing import Any
from scrapling.fetchers import Fetcher
from scrapling.parser import Selector
from utils.retry import retry
from utils.logger import setup_logger


class BaseScraper(ABC):
    def __init__(self, source_name: str, config: dict | None = None):
        self.source_name = source_name
        self.config = config or {}
        self.logger = setup_logger(f"scraper.{source_name}")
        self.default_headers = {
            "User-Agent": self.config.get(
                "user_agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
        }

    @abstractmethod
    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        pass

    @retry(max_attempts=3, delay=1.0)
    def _fetch(self, url: str, **kwargs) -> Selector:
        page = Fetcher.get(
            url,
            headers=self.default_headers,
            timeout=self.config.get("timeout", 30),
            follow_redirects=True,
            impersonate="chrome",
            **kwargs,
        )
        if page.status != 200:
            raise Exception(f"HTTP {page.status} for {url}")
        return page

    def close(self):
        pass
