import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scrapers.compliments.scraper import ComplimentsScraper


def test_extract_initial_state():
    scraper = ComplimentsScraper()
    html = '<html><script>window.__INITIAL_STATE__={"data":{"products":{"productEntities":{"abc":{"productId":"abc","brand":"Compliments","name":"Test Product","price":{"value":5.99,"currency":"CAD"},"image":{"src":"https://example.com/img.jpg"},"available":true,"categoryPath":[],"size":{}}}},"catalogue":{"data":{"totalProducts":1,"productGroups":[{"products":["abc"]}],"nextPageToken":null}}}}</script></html>'
    result = scraper._extract_initial_state(html)
    assert result is not None
    assert result["data"]["products"]["productEntities"]["abc"]["brand"] == "Compliments"


def test_parse_entity():
    scraper = ComplimentsScraper()
    entity = {
        "productId": "test-id",
        "retailerProductId": "12345EA",
        "brand": "Compliments",
        "name": "Test Product 500 g",
        "price": {"value": 4.99, "currency": "CAD"},
        "image": {"src": "https://example.com/img.jpg"},
        "available": True,
        "categoryPath": [{"name": "Groceries"}, {"name": "Produce"}],
        "size": {"value": "500 g"},
    }
    result = scraper._parse_entity(entity)
    assert result is not None
    assert result["product_name"] == "Test Product 500 g"
    assert result["price_cad"] == 4.99
    assert result["is_available"] is True


def test_scrape_all_from_html():
    scraper = ComplimentsScraper()
    result = scraper.scrape_all_from_html()
    assert len(result) > 0
    assert result[0]["brand"] == "Compliments"
