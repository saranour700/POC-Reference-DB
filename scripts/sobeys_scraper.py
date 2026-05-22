import httpx, re, json, time, concurrent.futures, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)

with open(DATA_DIR / 'slug_by_rid.json') as f:
    slug_by_rid = json.load(f)

# Load existing progress
products_path = DATA_DIR / 'sobeys_products.json'
nutrition_path = DATA_DIR / 'sobeys_nutrition.json'

existing_products = {}
existing_slugs = set()
if products_path.exists():
    with open(products_path) as f:
        for p in json.load(f):
            existing_products[p['sku']] = p
            slug = p.get('sobeys_url', '').split('/')[-1]
            existing_slugs.add(slug)

all_slugs = list(slug_by_rid.values())
remaining = [s for s in all_slugs if s not in existing_slugs]
print(f"Slugs: {len(all_slugs)} total, {len(existing_slugs)} done, {len(remaining)} remaining")

def parse_val(v):
    if not v: return None
    m = re.search(r'(\d+\.?\d*)', str(v))
    return float(m.group(1)) if m else None

def process_slug(slug):
    url = f"https://www.sobeys.com/products/{slug}"
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=10) as c:
            r = c.get(url)
            if r.status_code != 200 or 'application/ld+json' not in r.text:
                return None
            match = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.DOTALL)
            if not match: return None
            data = json.loads(match.group(1))
            if not isinstance(data, dict) or data.get('@type') != 'Product': return None
            n = data.get('nutrition', {})
            prod = {'sobeys_url': url, 'sku': data.get('sku'),
                'brand': data.get('brand', {}).get('name') if isinstance(data.get('brand'), dict) else data.get('brand'),
                'product_name': data.get('name'), 'description': data.get('description'),
                'image_url': data.get('image', [None])[0] if isinstance(data.get('image'), list) else data.get('image'),
                'price': data.get('offers', {}).get('price'), 'price_currency': data.get('offers', {}).get('priceCurrency'),
                'availability': data.get('offers', {}).get('availability'), 'source': 'sobeys'}
            nut = {'product_id': data.get('sku'), 'sobeys_url': url,
                'serving_size': n.get('servingSize'), 'calories': parse_val(n.get('calories')),
                'fat_g': parse_val(n.get('fatContent')), 'saturated_fat_g': parse_val(n.get('saturatedFatContent')),
                'trans_fat_g': parse_val(n.get('transFatContent')), 'cholesterol_mg': parse_val(n.get('cholesterolContent')),
                'sodium_mg': parse_val(n.get('sodiumContent')), 'potassium_mg': parse_val(n.get('potassiumContent')),
                'carbohydrate_g': parse_val(n.get('carbohydrateContent')), 'fibre_g': parse_val(n.get('fiberContent')),
                'sugars_g': parse_val(n.get('sugarContent')), 'protein_g': parse_val(n.get('proteinContent')),
                'calcium_mg': parse_val(n.get('calciumContent')), 'iron_mg': parse_val(n.get('ironContent'))}
            return prod, nut
    except:
        return None

all_products = dict(existing_products)
all_nutrition = {}
if nutrition_path.exists():
    with open(nutrition_path) as f:
        for n in json.load(f):
            all_nutrition[n['product_id']] = n

start = time.time()
BATCH_SIZE = 200
TOTAL = len(remaining)

if TOTAL == 0:
    print("All done!")
    sys.exit(0)

with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
    for batch_start in range(0, TOTAL, BATCH_SIZE):
        batch = remaining[batch_start:batch_start + BATCH_SIZE]
        futures = {executor.submit(process_slug, slug): slug for slug in batch}
        batch_count = 0
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            if r:
                prod, nut = r
                all_products[prod['sku']] = prod
                all_nutrition[nut['product_id']] = nut
                batch_count += 1

        elapsed = time.time() - start
        done = batch_start + len(batch)
        total_processed = len(existing_slugs) + done
        rate = done / elapsed if elapsed > 0 else 0
        remaining_eta = (TOTAL - done) / rate if rate > 0 else 0
        print(f"Batch {batch_start//BATCH_SIZE + 1}/{(TOTAL+BATCH_SIZE-1)//BATCH_SIZE}: +{batch_count} ({len(all_products)} total, {done}/{TOTAL} remaining, {elapsed:.0f}s, {rate:.0f}/s, ETA: {remaining_eta:.0f}s)")

        with open(products_path, 'w') as f:
            json.dump(list(all_products.values()), f)
        with open(nutrition_path, 'w') as f:
            json.dump(list(all_nutrition.values()), f)

total_time = time.time() - start
print(f"COMPLETE: {len(all_products)} products, {len(all_nutrition)} nutrition in {total_time:.0f}s")
