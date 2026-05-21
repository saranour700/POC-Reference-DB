RAW_SCHEMA = {
    "productId": "VARCHAR",
    "retailerProductId": "VARCHAR",
    "brand": "VARCHAR",
    "name": "VARCHAR",
    "available": "BOOLEAN",
    "price_value": "DECIMAL(10,2)",
    "price_currency": "VARCHAR",
    "size_value": "VARCHAR",
    "image_url": "VARCHAR",
    "category_path": "VARCHAR",
    "source": "VARCHAR",
    "scraped_at": "TIMESTAMP",
}

RAW_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS {table} (
    id INTEGER PRIMARY KEY,
    product_id VARCHAR,
    retailer_product_id VARCHAR,
    brand VARCHAR,
    name VARCHAR,
    available BOOLEAN,
    price_value DECIMAL(10,2),
    price_currency VARCHAR,
    size_value VARCHAR,
    image_url VARCHAR,
    category_path VARCHAR,
    source VARCHAR,
    scraped_at TIMESTAMP,
    raw_json JSON
);
"""
