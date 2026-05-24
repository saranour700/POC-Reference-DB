DIM_CANONICAL_PRODUCTS = {
    "canonical_id": "VARCHAR",
    "brand": "VARCHAR",
    "product_type": "VARCHAR",
    "product_name": "VARCHAR",
    "description": "VARCHAR",
    "image_url": "VARCHAR",
    "category": "VARCHAR",
    "primary_source": "VARCHAR",
    "is_active": "BOOLEAN",
    "created_at": "VARCHAR",
}

DIM_PRODUCT_VARIANTS = {
    "variant_id": "VARCHAR",
    "canonical_id": "VARCHAR",
    "product_id": "VARCHAR",
    "source": "VARCHAR",
    "product_name": "VARCHAR",
    "quantity": "DECIMAL(12,4)",
    "quantity_unit": "VARCHAR",
    "pack_count": "INTEGER",
    "price_cad": "DECIMAL(10,2)",
    "price_per_unit": "DECIMAL(10,4)",
    "image_url": "VARCHAR",
    "is_available": "BOOLEAN",
}

FCT_PRODUCT_SOURCES = {
    "product_id": "VARCHAR",
    "canonical_id": "VARCHAR",
    "source": "VARCHAR",
    "source_product_id": "VARCHAR",
    "source_url": "VARCHAR",
    "price_cad": "DECIMAL(10,2)",
    "is_available": "BOOLEAN",
    "scraped_at": "VARCHAR",
}

DIM_NUTRITION = {
    "nutrition_id": "VARCHAR",
    "product_id": "VARCHAR",
    "canonical_id": "VARCHAR",
    "serving_size": "VARCHAR",
    "calories": "INTEGER",
    "fat_g": "DECIMAL(8,2)",
    "saturated_fat_g": "DECIMAL(8,2)",
    "trans_fat_g": "DECIMAL(8,2)",
    "cholesterol_mg": "DECIMAL(8,2)",
    "sodium_mg": "DECIMAL(8,2)",
    "potassium_mg": "DECIMAL(8,2)",
    "carbohydrate_g": "DECIMAL(8,2)",
    "fibre_g": "DECIMAL(8,2)",
    "sugars_g": "DECIMAL(8,2)",
    "protein_g": "DECIMAL(8,2)",
    "calcium_mg": "DECIMAL(8,2)",
    "iron_mg": "DECIMAL(8,2)",
    "source": "VARCHAR",
}
