#!/usr/bin/env python3
"""تحليل كل الـ datasets المرفوعة على HuggingFace"""

import json
from datasets import load_dataset

import os
from dotenv import load_dotenv
load_dotenv()
if os.getenv("HF_TOKEN"):
    os.environ["HF_TOKEN"] = os.getenv("HF_TOKEN")
elif os.getenv("HUGGINGFACE_TOKEN"):
    os.environ["HF_TOKEN"] = os.getenv("HUGGINGFACE_TOKEN")

# -------------------- تحميل الـ 4 datasets --------------------
datasets = {
    "voila-compliments-products": load_dataset("saraNour/voila-compliments-products", split="train"),
    "voila-compliments-nutrition": load_dataset("saraNour/voila-compliments-nutrition", split="train"),
    "alimentsduquebec-products": load_dataset("saraNour/alimentsduquebec-products", split="train"),
    "madeinca-canadian-brands": load_dataset("saraNour/madeinca-canadian-brands", split="train"),
}

summary = {}

# -------------------- عرض الـ schema + 3 samples لكل dataset --------------------
for name, ds in datasets.items():
    print(f"\n{'='*60}")
    print(f"📦 {name}")
    print(f"{'='*60}")

    # Schema
    print(f"\n▶ Schema ({len(ds.features)} columns):")
    for col, feat in ds.features.items():
        print(f"  {col}: {feat.dtype if hasattr(feat, 'dtype') else type(feat).__name__}")

    # 3 samples
    print(f"\n▶ 3 sample rows:")
    for i in range(min(3, len(ds))):
        row = ds[i]
        # Show first 150 chars per value for readability
        preview = {k: str(v)[:150] for k, v in row.items()}
        print(f"  Row {i}: {json.dumps(preview, ensure_ascii=False, default=str)[:500]}")

    # Missing values % - use efficient batch sampling
    total = len(ds)
    print(f"\n▶ Missing values % (total rows: {total}):")
    missing_info = {}
    # Sample up to 2000 rows for speed
    sample_size = min(total, 2000)
    sample = ds.select(range(sample_size))
    for col in ds.features:
        null_count = sum(
            1 for i in range(sample_size)
            if sample[i][col] is None or sample[i][col] == "" or sample[i][col] == []
        )
        pct = round(null_count / sample_size * 100, 1)
        missing_info[col] = {"null_count": null_count, "null_pct": pct}
        print(f"  {col}: {null_count}/{sample_size} ({pct}%)")
    summary[name] = {
        "rows": total,
        "cols": len(ds.features),
        "missing": missing_info,
    }

# -------------------- التحقق من product_id في voila-compliments-products وبناء URLs --------------------
print(f"\n{'='*60}")
print(f"🔗 URL Construction for voila-compliments-products")
print(f"{'='*60}")

ds = datasets["voila-compliments-products"]
cols = ds.features.keys()

# تحديد العمود اللي ممكن نستخدمه كـ product_id
product_id_col = None
if "product_id" in cols:
    product_id_col = "product_id"
elif "id" in cols:
    product_id_col = "id"
elif "sku" in cols:
    product_id_col = "sku"

print(f"\nAvailable columns: {list(cols)}")
print(f"Using column for URL: {product_id_col}")

if product_id_col:
    url_count = 0
    urls = []
    for i in range(len(ds)):
        pid = ds[i][product_id_col]
        if pid and str(pid).strip():
            url = f"https://voila.ca/products/{pid}"
            urls.append(url)
            url_count += 1
    print(f"Total rows: {len(ds)}")
    print(f"Rows with valid {product_id_col}: {url_count}")
    print(f"Sample URLs (first 3):")
    for u in urls[:3]:
        print(f"  {u}")
    summary["voila_urls"] = {
        "total_rows": len(ds),
        "valid_ids": url_count,
        "sample_urls": urls[:5],
        "column_used": product_id_col,
    }
else:
    print("⚠️  No suitable product ID column found!")
    summary["voila_urls"] = {"error": "No product ID column found"}

# -------------------- طباعة ملخص JSON في النهاية --------------------
print(f"\n{'='*60}")
print(f"📊 JSON Summary")
print(f"{'='*60}")
print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
