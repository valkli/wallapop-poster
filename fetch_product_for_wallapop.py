#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_product_for_wallapop.py
Fetches the next product ready for Wallapop publication from Notion DBs.

Filters:
  - Wallapop Posted = empty  (not yet published)
  - In Stock = False         (out of physical stock → designated for online sale)
  - donde = "magazin" OR "sklad"
  - Selling Price > 15 EUR

Sources (round-robin):
  DB1: Product_Variants_GangaBox   (2bd12f742f9e8198bfb3dce06af14f58)
  DB2: Product_Variants             (27f12f742f9e81648959ee3d597c4e7e)

Saves result to: wallapop-poster/temp/product_data.json
Prints: OK <product_name> | NO_PRODUCTS
"""

import os
import sys
import json
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

NOTION_API_KEY = os.getenv('NOTION_API_KEY')

DB1_ID = '2bd12f742f9e8198bfb3dce06af14f58'   # Product_Variants_GangaBox
DB2_ID = os.getenv('WALLAPOP_DB2_ID', '27f12f742f9e81648959ee3d597c4e7e')  # Product_Variants

MIN_PRICE = 15.0

HEADERS = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

OUT_DIR  = Path(__file__).parent / 'temp'
OUT_FILE = OUT_DIR / 'product_data.json'
CURSOR_FILE = OUT_DIR / 'wal_db_cursor.json'
FAILED_TODAY_FILE = OUT_DIR / 'failed_today.json'
PUBLISHED_TODAY_FILE = OUT_DIR / 'published_today.json'


def load_local_skip_ids() -> set[str]:
    ids = set()
    for path in (FAILED_TODAY_FILE, PUBLISHED_TODAY_FILE):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            ids.update(x for x in data.get('ids', []) if x)
        except Exception:
            pass
    return ids


def get_next_db_id():
    """Round-robin between DB1 and DB2."""
    CURSOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    if CURSOR_FILE.exists():
        try:
            state = json.loads(CURSOR_FILE.read_text())
            last = state.get('last_db', 1)
        except Exception:
            last = 1
    else:
        last = 1

    next_db = 2 if last == 1 else 1
    CURSOR_FILE.write_text(json.dumps({'last_db': next_db}))
    return (DB1_ID if next_db == 1 else DB2_ID), next_db


def build_filter():
    """
    Wallapop publication filter:
      - Wallapop Posted empty (not yet published)
      - In Stock = False  (out of physical stock → online liquidation)
      - donde = magazin OR sklad
      - Selling Price > 15
    """
    return {
        "and": [
            {
                "property": "Wallapop Posted",
                "rich_text": {"is_empty": True}
            },
            {
                "property": "In Stock",
                "checkbox": {"equals": False}
            },
            {
                "or": [
                    {"property": "donde", "rich_text": {"contains": "magazin"}},
                    {"property": "donde", "rich_text": {"contains": "sklad"}}
                ]
            },
            {
                "property": "Selling Price",
                "number": {"greater_than": MIN_PRICE}
            }
        ]
    }


def fetch_next_pending(db_id):
    """Query Notion for the next matching product in db_id. Returns page or None."""
    skip_ids = load_local_skip_ids()
    payload = {
        "filter": build_filter(),
        "sorts": [{"property": "Created time", "direction": "ascending"}],
        "page_size": 25
    }
    resp = requests.post(
        f'https://api.notion.com/v1/databases/{db_id}/query',
        headers=HEADERS, json=payload
    )
    if resp.status_code == 404:
        print(f'ERROR: DB {db_id} not found', file=sys.stderr)
        return None
    if resp.status_code != 200:
        print(f'ERROR: Notion {resp.status_code}: {resp.text[:200]}')
        sys.exit(1)
    results = resp.json().get('results', [])
    for page in results:
        if page.get('id') not in skip_ids:
            return page
    return None


def fetch_from_any_db():
    """Try round-robin DB, fallback to the other. Returns (page, db_id) or (None, None)."""
    db_id, _ = get_next_db_id()
    page = fetch_next_pending(db_id)
    if page:
        return page, db_id

    other = DB2_ID if db_id == DB1_ID else DB1_ID
    page = fetch_next_pending(other)
    return (page, other) if page else (None, None)


def extract_product(page, db_id):
    """Extract relevant fields from a Notion page object."""
    props = page['properties']
    data = {
        'notion_id': page['id'],
        'db_id': db_id,
        'properties': {}
    }

    extractors = {
        'title':        lambda p: p['title'][0]['text']['content'] if p.get('title') else '',
        'rich_text':    lambda p: p['rich_text'][0]['text']['content'] if p.get('rich_text') else '',
        'number':       lambda p: p.get('number'),
        'select':       lambda p: p['select']['name'] if p.get('select') else None,
        'multi_select': lambda p: [s['name'] for s in p.get('multi_select', [])],
        'url':          lambda p: p.get('url'),
        'checkbox':     lambda p: p.get('checkbox'),
        'files':        lambda p: [
            f['file']['url'] if f.get('file') else f['external']['url']
            for f in p.get('files', [])
        ],
    }

    for key, prop in props.items():
        ptype = prop.get('type')
        if ptype in extractors:
            try:
                data['properties'][key] = extractors[ptype](prop)
            except (KeyError, IndexError):
                data['properties'][key] = None

    if page.get('cover'):
        cover = page['cover']
        if cover.get('external'):
            data['cover_url'] = cover['external']['url']
        elif cover.get('file'):
            data['cover_url'] = cover['file']['url']

    return data


def count_pending(db_id):
    """Return approximate count of pending products in db_id."""
    payload = {"filter": build_filter(), "page_size": 1}
    resp = requests.post(
        f'https://api.notion.com/v1/databases/{db_id}/query',
        headers=HEADERS, json=payload
    )
    if resp.status_code != 200:
        return '?'
    d = resp.json()
    return '100+' if d.get('has_more') else str(len(d.get('results', [])))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not NOTION_API_KEY:
        print('ERROR: NOTION_API_KEY not set')
        sys.exit(1)

    product, db_id = fetch_from_any_db()

    if not product:
        print('NO_PRODUCTS')
        if OUT_FILE.exists():
            OUT_FILE.unlink()
        sys.exit(0)

    data = extract_product(product, db_id)
    props = data['properties']
    name   = props.get('Name', 'Unknown')
    price  = props.get('Selling Price', 0)
    donde  = props.get('donde', '?')
    weight = (props.get('Weight') or 0)
    images = len(props.get('Image') or [])

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    pending  = count_pending(db_id)
    db_label = 'DB1' if db_id == DB1_ID else 'DB2'
    print(f'OK {name} | price={price}€ | donde={donde} | {db_label} | remaining~{pending}')
    print(f'  Weight: {weight}g | Images: {images} | Notion ID: {data["notion_id"]}')


if __name__ == '__main__':
    main()
