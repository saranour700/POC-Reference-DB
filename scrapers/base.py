import httpx
from abc import ABC, abstractmethod
from typing import Any
from utils.retry import retry
from utils.logger import setup_logger


class BaseScraper(ABC):
    def __init__(self, source_name: str, config: dict | None = None):
        self.source_name = source_name
        self.config = config or {}
        self.logger = setup_logger(f"scraper.{source_name}")
        self.client = httpx.Client(
            follow_redirects=True,
            timeout=self.config.get("timeout", 30),
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-CA,en;q=0.9",
            },
        )

    @abstractmethod
    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        pass

    @retry(max_attempts=3, delay=1.0)
    def _fetch(self, url: str) -> httpx.Response:
        resp = self.client.get(url)
        resp.raise_for_status()
        return resp

    def close(self):
        self.client.close()
