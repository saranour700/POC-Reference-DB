import re


def validate_price(price: float | None) -> float | None:
    if price is None:
        return None
    try:
        return round(float(price), 2)
    except (ValueError, TypeError):
        return None


def validate_sku(sku: str | None) -> str | None:
    if not sku:
        return None
    return sku.strip().upper()


def validate_image_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    return None


def extract_size_from_name(name: str) -> str | None:
    patterns = [
        r'(\d+[\s-]*(?:g|kg|ml|l|oz|lb|count|pack|pieces?))',
        r'(\d+\s*x\s*\d+\s*g)',
    ]
    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(1)
    return None
