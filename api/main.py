import json
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PARQUET = DATA_DIR / "canonical_products.parquet"
JSONL = DATA_DIR / "canonical_products.jsonl"


# ── Pydantic models ──

class NutritionOut(BaseModel):
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbohydrate_g: Optional[float] = None
    sodium_mg: Optional[float] = None


class AdqMatchOut(BaseModel):
    matched: bool = False
    adq_name: Optional[str] = None
    adq_brand: Optional[str] = None
    adq_certification: Optional[str] = None
    adq_subcategory: Optional[str] = None
    match_score: Optional[float] = None


class ProductOut(BaseModel):
    canonical_id: str
    name: str
    brand: Optional[str] = None
    price_cad: Optional[float] = None
    size_value: Optional[float] = None
    size_unit: Optional[str] = None
    pack_type: Optional[str] = None
    language: Optional[str] = None
    image_url: Optional[str] = None
    url_voila: Optional[str] = None
    category: Optional[str] = None
    is_available: bool = True
    sources: list[str] = []
    nutrition: NutritionOut = NutritionOut()
    adq_match: Optional[AdqMatchOut] = None


class ProductListOut(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[ProductOut]


class CategoryCount(BaseModel):
    category: str
    product_count: int


class StatsOut(BaseModel):
    total_products: int
    with_nutrition: int
    multi_source: int
    avg_price: Optional[float] = None
    categories_count: int


# ── App ──

app = FastAPI(
    title="Canonical Products API",
    description="Reference database of Canadian grocery products",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores
df: pd.DataFrame | None = None
entities: list[dict] = []


def _v(val):
    """Convert pandas NaN to None for Optional fields."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return val


def _row_to_product(row: pd.Series) -> dict:
    """Convert a parquet row to a nested product dict."""
    nutrition = NutritionOut(
        calories=_v(row.get("nutri_calories")),
        protein_g=_v(row.get("nutri_protein_g")),
        fat_g=_v(row.get("nutri_fat_g")),
        carbohydrate_g=_v(row.get("nutri_carbohydrate_g")),
        sodium_mg=_v(row.get("nutri_sodium_mg")),
    )
    adq = None
    if row.get("adq_matched"):
        adq = AdqMatchOut(
            matched=True,
            adq_name=_v(row.get("adq_name")),
            adq_brand=_v(row.get("adq_brand")),
            adq_certification=_v(row.get("adq_certification")),
            adq_subcategory=_v(row.get("adq_subcategory")),
            match_score=_v(row.get("adq_score")),
        )

    sources_raw = row.get("sources")
    if isinstance(sources_raw, str):
        sources = [s.strip() for s in sources_raw.split(",") if s.strip()]
    elif isinstance(sources_raw, list):
        sources = sources_raw
    else:
        sources = ["voila"]

    product = {
        "canonical_id": row["canonical_id"],
        "name": row["name"],
        "brand": _v(row.get("brand")),
        "price_cad": _v(row.get("price_cad")),
        "size_value": _v(row.get("size_value")),
        "size_unit": _v(row.get("size_unit")),
        "pack_type": _v(row.get("pack_type")),
        "language": _v(row.get("language")),
        "image_url": _v(row.get("image_url")),
        "url_voila": _v(row.get("url_voila")),
        "category": _v(row.get("category")),
        "is_available": bool(row.get("is_available", True)),
        "sources": sources,
        "nutrition": nutrition,
        "adq_match": adq,
    }
    return product


@app.on_event("startup")
async def load_data():
    global df, entities
    df = pd.read_parquet(PARQUET)
    # Load full nested entities from JSONL for detail endpoint
    with open(JSONL) as f:
        for line in f:
            entities.append(json.loads(line))
    print(f"Loaded {len(df)} products")


# ── Endpoints ──

@app.get("/products", response_model=ProductListOut)
async def list_products(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    has_nutrition: Optional[bool] = Query(None),
    is_available: Optional[bool] = Query(True),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    filtered = df.copy()

    if search:
        mask = filtered["name"].str.contains(search, case=False, na=False)
        filtered = filtered[mask]

    if category:
        cat_lower = category.strip().lower()
        mask = filtered["category"].str.lower().str.strip() == cat_lower
        filtered = filtered[mask]

    if has_nutrition is not None:
        if has_nutrition:
            mask = filtered["nutri_calories"].notna()
        else:
            mask = filtered["nutri_calories"].isna()
        filtered = filtered[mask]

    if is_available is not None:
        mask = filtered["is_available"] == is_available
        filtered = filtered[mask]

    total = len(filtered)
    sliced = filtered.iloc[offset : offset + limit]
    items = [_row_to_product(row) for _, row in sliced.iterrows()]

    return ProductListOut(total=total, offset=offset, limit=limit, items=items)


@app.get("/products/{canonical_id}", response_model=ProductOut)
async def get_product(canonical_id: str):
    for ent in entities:
        if ent["canonical_id"] == canonical_id:
            nut = ent.get("nutrition", {}) or {}
            nutrition = NutritionOut(
                calories=nut.get("calories"),
                protein_g=nut.get("protein_g"),
                fat_g=nut.get("fat_g"),
                carbohydrate_g=nut.get("carbohydrate_g"),
                sodium_mg=nut.get("sodium_mg"),
            )
            aq = ent.get("adq_match")
            adq = None
            if aq and aq.get("matched"):
                adq = AdqMatchOut(
                    matched=True,
                    adq_name=aq.get("adq_name"),
                    adq_brand=aq.get("adq_brand"),
                    adq_certification=aq.get("adq_certification"),
                    adq_subcategory=aq.get("adq_subcategory"),
                    match_score=aq.get("adq_score"),
                )
            sources = ent.get("sources", ["voila"])
            return ProductOut(
                canonical_id=ent["canonical_id"],
                name=ent["name"],
                brand=_v(ent.get("brand")),
                price_cad=_v(ent.get("price_cad")),
                size_value=_v(ent.get("size_value")),
                size_unit=_v(ent.get("size_unit")),
                pack_type=_v(ent.get("pack_type")),
                language=_v(ent.get("language")),
                image_url=_v(ent.get("image_url")),
                url_voila=_v(ent.get("url_voila")),
                category=_v(ent.get("category")),
                is_available=bool(ent.get("is_available", True)),
                sources=sources,
                nutrition=nutrition,
                adq_match=adq,
            )
    raise HTTPException(status_code=404, detail=f"Product not found: {canonical_id}")


@app.get("/categories")
async def list_categories():
    counts = df["category"].value_counts()
    items = [
        CategoryCount(category=cat, product_count=int(cnt))
        for cat, cnt in counts.items()
        if pd.notna(cat) and cat
    ]
    items.sort(key=lambda x: -x.product_count)
    return items


@app.get("/stats", response_model=StatsOut)
async def get_stats():
    total = len(df)
    with_nutrition = int(df["nutri_calories"].notna().sum())
    multi_source = int((df["sources"].apply(
        lambda s: len([x for x in str(s).split(",") if x.strip()]) > 1 if pd.notna(s) else False
    )).sum())
    avg_price = float(df["price_cad"].mean()) if df["price_cad"].notna().any() else None
    categories_count = int(df["category"].nunique())
    return StatsOut(
        total_products=total,
        with_nutrition=with_nutrition,
        multi_source=multi_source,
        avg_price=round(avg_price, 2) if avg_price else None,
        categories_count=categories_count,
    )


@app.get("/")
async def root():
    return {
        "api": "Canonical Products API",
        "docs": "/docs",
        "endpoints": {
            "products": "GET /products",
            "product_detail": "GET /products/{canonical_id}",
            "categories": "GET /categories",
            "stats": "GET /stats",
        },
    }
