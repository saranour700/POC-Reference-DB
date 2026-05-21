VALIDATION_RULES = {
    "product_id": {"required": True, "type": "string", "unique": True},
    "retailer_product_id": {"required": True, "type": "string"},
    "brand": {"required": True, "type": "string"},
    "product_name": {"required": True, "type": "string", "min_length": 3},
    "price_cad": {"required": True, "type": "number", "min": 0},
    "is_available": {"required": True, "type": "boolean"},
}
