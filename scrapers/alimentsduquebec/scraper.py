import json, re, time, html as html_mod
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import requests
from scrapling.parser import Selector

from scrapers.base import BaseScraper
from utils.logger import setup_logger


CATEGORIES = [
    "assaisonnements-sauces-et-condiments",
    "boissons",
    "boissons-alcoolisees",
    "boulangerie-patisserie-et-desserts",
    "collation",
    "confiseries-et-produits-sucres",
    "fruits-et-legumes",
    "huiles-et-autres-matieres-grasses",
    "mets-prepares",
    "nourriture-pour-animaux",
    "poissons-et-fruits-de-mer",
    "produits-cerealiers",
    "produits-laitiers-et-substituts",
    "produits-vegetariens",
    "viandes",
]

SPRIG_URL = "https://alimentsduquebec.com/index.php?p=actions/sprig-core/components/render"


class AlimentsDuQuebecScraper(BaseScraper):
    def __init__(self, config: dict | None = None):
        super().__init__("alimentsduquebec", config)
        self.logger = setup_logger("scraper.alimentsduquebec")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        self.urls_file = Path("data/alimentsduquebec_product_urls.json")
        self.products_file = Path("data/alimentsduquebec_products.json")

    def scrape(self, **kwargs) -> list[dict[str, Any]]:
        collect_urls = kwargs.get("collect_urls", True)
        scrape_pages = kwargs.get("scrape_pages", True)

        if collect_urls or not self.urls_file.exists():
            self._collect_all_urls()

        if scrape_pages:
            return self._scrape_all_products()
        return []

    def _collect_all_urls(self) -> list[str]:
        all_urls = set()
        seen_category_slugs = set()

        for cat_slug in CATEGORIES:
            cat_start = time.time()
            urls = self._collect_category_urls(cat_slug)
            new_slugs = {u.split("/")[-1] for u in urls}
            overlap = len(new_slugs & seen_category_slugs)
            seen_category_slugs.update(new_slugs)
            all_urls.update(urls)
            self.logger.info(
                f"  {cat_slug}: {len(urls)} URLs (+{len(urls) - overlap} new, "
                f"{overlap} overlap) in {time.time()-cat_start:.0f}s"
            )

        url_list = sorted(all_urls)
        with open(self.urls_file, "w") as f:
            json.dump(url_list, f, indent=2)
        self.logger.info(f"Total unique product URLs: {len(url_list)}")
        return url_list

    def _collect_category_urls(self, cat_slug: str) -> list[str]:
        url = f"https://alimentsduquebec.com/aliments-dici/{cat_slug}"
        resp = self.session.get(url, timeout=30)
        if resp.status_code != 200:
            self.logger.warning(f"  {cat_slug}: HTTP {resp.status_code}")
            return []

        config_raw = self._extract_sprig_config(resp.text)
        if not config_raw:
            self.logger.warning(f"  {cat_slug}: no Sprig config found")
            return []

        total, first_page_urls = self._parse_listing_page(resp.text, cat_slug)
        urls = set(first_page_urls)

        if total is None:
            count_match = re.search(r"sur\s+([\d,]+)\s", resp.text)
            if count_match:
                total = int(count_match.group(1).replace(",", ""))
            else:
                total = len(urls) if urls else 12

        pages_needed = (total + 11) // 12
        self.logger.info(f"  {cat_slug}: {total} products, ~{pages_needed} pages")

        for page in range(2, pages_needed + 1):
            more = self._fetch_sprig_page(cat_slug, config_raw, page)
            urls.update(more)

        return sorted(urls)

    def _extract_sprig_config(self, html_text: str) -> str | None:
        match = re.search(r'data-hx-vals="([^"]+)"', html_text)
        if not match:
            return None
        raw = html_mod.unescape(match.group(1))
        try:
            data = json.loads(raw)
            return data.get("sprig:config")
        except json.JSONDecodeError:
            return None

    def _parse_listing_page(self, html_text: str, cat_slug: str) -> tuple[int | None, list[str]]:
        urls = re.findall(
            rf'href="(https://alimentsduquebec\.com/aliments-dici/{cat_slug}/[^"]+)"',
            html_text,
        )
        count_match = re.search(r"sur\s+([\d,]+)", html_text)
        total = int(count_match.group(1).replace(",", "")) if count_match else None
        return total, list(set(urls))

    def _fetch_sprig_page(self, cat_slug: str, sprig_config: str, page: int) -> list[str]:
        params = {
            "sprig:config": sprig_config,
            "page": page,
            "tab": "products",
        }
        headers = {
            "HX-Request": "true",
            "HX-Target": "listing",
            "HX-Current-URL": f"https://alimentsduquebec.com/aliments-dici/{cat_slug}",
            "Referer": f"https://alimentsduquebec.com/aliments-dici/{cat_slug}",
        }
        try:
            resp = self.session.get(SPRIG_URL, params=params, headers=headers, timeout=30)
            if resp.status_code != 200:
                return []
            return list(set(re.findall(r'href="(https://alimentsduquebec\.com/aliments-dici/[^"]+)"', resp.text)))
        except Exception:
            return []

    def _scrape_all_products(self) -> list[dict[str, Any]]:
        if not self.urls_file.exists():
            self.logger.error("No product URLs file. Run with collect_urls=True first.")
            return []

        with open(self.urls_file) as f:
            all_urls = json.load(f)

        existing = {}
        if self.products_file.exists():
            with open(self.products_file) as f:
                for p in json.load(f):
                    existing[p["url"]] = p

        remaining = [u for u in all_urls if u not in existing]
        self.logger.info(f"Products: {len(existing)} done, {len(remaining)} remaining")

        if not remaining:
            return list(existing.values())

        import concurrent.futures

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(self._scrape_product, url): url for url in remaining}
            done_count = len(existing)
            for future in concurrent.futures.as_completed(futures):
                url = futures[future]
                result = future.result()
                if result:
                    existing[url] = result
                    done_count += 1

                if done_count % 100 == 0:
                    elapsed = time.time() - start
                    rate = done_count / elapsed if elapsed > 0 else 0
                    self.logger.info(
                        f"  {done_count}/{len(all_urls)} ({rate:.1f}/s, "
                        f"ETA: {(len(all_urls)-done_count)/rate:.0f}s)"
                    )
                    with open(self.products_file, "w") as f:
                        json.dump(list(existing.values()), f, indent=2)

        with open(self.products_file, "w") as f:
            json.dump(list(existing.values()), f, indent=2)

        total_time = time.time() - start
        self.logger.info(f"COMPLETE: {len(existing)} products in {total_time:.0f}s")
        return list(existing.values())

    def _scrape_product(self, url: str) -> dict[str, Any] | None:
        try:
            resp = self.session.get(url, timeout=15)
            if resp.status_code != 200:
                return None
            page = Selector(resp.text)
            return self._parse_product(page, url)
        except Exception:
            return None

    def _parse_product(self, page: Selector, url: str) -> dict[str, Any] | None:
        scripts = page.css('script[type="application/ld+json"]')
        if not scripts:
            return None
        try:
            raw = json.loads(scripts[0].text)
        except (json.JSONDecodeError, IndexError):
            return None

        graph = raw.get("@graph", [raw])
        product = None
        for item in graph:
            if item.get("@type") == "Product":
                product = item
                break
        if not product:
            return None

        brand_raw = product.get("brand", {})
        brand = brand_raw.get("name") if isinstance(brand_raw, dict) else brand_raw

        img = product.get("image")
        image = img[0] if isinstance(img, list) else img

        offers = product.get("offers", {}) or {}
        price = offers.get("price") if isinstance(offers, dict) else None

        cert = product.get("hasCertification", {})
        if isinstance(cert, list):
            certification = cert[0].get("name") if cert else None
        elif isinstance(cert, dict):
            certification = cert.get("name")
        else:
            certification = str(cert) if cert else None

        tags = page.css(".hero-content .tags .tag")
        subcategory = tags[0].get_all_text().strip() if tags else ""

        formats = []
        accordion = page.css(".accordion-content")
        for a in accordion:
            lis = a.find_all("li")
            texts = [li.get_all_text().strip() for li in lis]
            if texts and any(
                re.search(r'\d+\s*(g|mL|kg|lb|oz|L|cl|ml)', t, re.IGNORECASE)
                for t in texts
            ):
                formats = texts
                break

        desc_el = page.css(".hero-description .description-short")
        description = desc_el[0].get_all_text().strip() if desc_el else product.get("description", "")

        return {
            "url": url,
            "sku": product.get("sku"),
            "name": product.get("name"),
            "description": description,
            "brand": brand,
            "image_url": image,
            "price": price,
            "price_currency": offers.get("priceCurrency") if isinstance(offers, dict) else None,
            "offers_url": offers.get("url") if isinstance(offers, dict) else None,
            "certification": certification,
            "subcategory": subcategory,
            "formats": formats,
            "source": "alimentsduquebec",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }

    def close(self):
        self.session.close()
