NORMALIZED_SCHEMA = {
    "product_id": "VARCHAR",
    "retailer_product_id": "VARCHAR",
    "brand": "VARCHAR",
    "product_name": "VARCHAR",
    "size": "VARCHAR",
    "price_cad": "DECIMAL(10,2)",
    "image_url": "VARCHAR",
    "category": "VARCHAR",
    "source_url": "VARCHAR",
    "is_available": "BOOLEAN",
    "scraped_at": "DATE",
}

NORMALIZED_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS {table} (
    id INTEGER PRIMARY KEY,
    product_id VARCHAR,
    retailer_product_id VARCHAR,
    brand VARCHAR,
    product_name VARCHAR,
    size VARCHAR,
    price_cad DECIMAL(10,2),
    image_url VARCHAR,
    category VARCHAR,
    source_url VARCHAR,
    is_available BOOLEAN,
    scraped_at DATE
);
"""
