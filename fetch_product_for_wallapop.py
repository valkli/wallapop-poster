#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_product_for_wallapop.py
Fetches the next UNPUBLISHED product from Notion DB (Product_Variants_GangaBox).

Filters:
  - Wallapop Posted = empty (not yet published on Wallapop)
  - In Stock = true

Saves result to: wallapop-poster/temp/product_data.json
Prints: OK <product_name> | remaining: N | NO_PRODUCTS
"""

import os
import sys
import json
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

NOTION_API_KEY = os.getenv('NOTION_API_KEY')
DB_ID = '2bd12f742f9e8198bfb3dce06af14f58'  # Product_Variants_GangaBox

HEADERS = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

OUT_DIR = Path(__file__).parent / 'temp'
OUT_FILE = OUT_DIR / 'product_data.json'


def fetch_next_pending():
    """
    Query Notion for the next product where:
      - In Stock = true
      - Wallapop Posted = empty
    Returns first match or None.
    """
    payload = {
        "filter": {
            "and": [
                {
                    "property": "In Stock",
                    "checkbox": {"equals": True}
                },
                {
                    "property": "Wallapop Posted",
                    "rich_text": {"is_empty": True}
                }
            ]
        },
        "sorts": [
            {"property": "Created time", "direction": "ascending"}
        ],
        "page_size": 1
    }

    resp = requests.post(
        f'https://api.notion.com/v1/databases/{DB_ID}/query',
        headers=HEADERS,
        json=payload
    )

    if resp.status_code == 404:
        print('ERROR: DB not found. Check DB_ID or if "Wallapop Posted" field exists in Notion.')
        print('Create a "Wallapop Posted" text field in the Notion DB first.')
        sys.exit(1)

    if resp.status_code != 200:
        print(f'ERROR: Notion API {resp.status_code}: {resp.text[:200]}')
        sys.exit(1)

    results = resp.json().get('results', [])
    return results[0] if results else None


def extract_product(page):
    """Extract relevant fields from a Notion page object."""
    props = page['properties']
    data = {
        'notion_id': page['id'],
        'db_id': DB_ID,
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

    # Cover image
    if page.get('cover'):
        cover = page['cover']
        if cover.get('external'):
            data['cover_url'] = cover['external']['url']
        elif cover.get('file'):
            data['cover_url'] = cover['file']['url']

    return data


def build_wallapop_summary(data):
    """
    Build a summary text for Wallapop AI (max 50 chars).
    Format: "<Name> <Category>"
    """
    props = data['properties']
    name = (props.get('Name') or '').strip()
    category = (props.get('Category') or '').strip()

    summary = name
    if category and len(summary) + len(category) + 1 <= 48:
        summary = f"{summary} {category}"

    return summary[:50]


def count_pending():
    """Count how many products are still pending Wallapop publication."""
    payload = {
        "filter": {
            "and": [
                {"property": "In Stock", "checkbox": {"equals": True}},
                {"property": "Wallapop Posted", "rich_text": {"is_empty": True}}
            ]
        },
        "page_size": 1
    }
    resp = requests.post(
        f'https://api.notion.com/v1/databases/{DB_ID}/query',
        headers=HEADERS,
        json=payload
    )
    data = resp.json()
    has_more = data.get('has_more', False)
    results_count = len(data.get('results', []))
    return '100+' if has_more else str(results_count)


def main():
    if not NOTION_API_KEY:
        print('ERROR: NOTION_API_KEY environment variable not set')
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    product = fetch_next_pending()

    if not product:
        print('NO_PRODUCTS')
        if OUT_FILE.exists():
            OUT_FILE.unlink()
        sys.exit(0)

    data = extract_product(product)
    name = data['properties'].get('Name', 'Unknown')

    # Add wallapop-specific summary
    data['wallapop_summary'] = build_wallapop_summary(data)

    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    pending = count_pending()
    print(f'OK {name} | remaining: {pending}')
    print(f'Summary for Wallapop: "{data["wallapop_summary"]}"')

    # Print key fields for easy review
    props = data['properties']
    print(f'  Price: {props.get("Selling Price")}€')
    print(f'  Weight: {props.get("Weight")}g → {(props.get("Weight") or 0)/1000:.1f}kg')
    print(f'  Images: {len(props.get("Image") or [])} images')
    print(f'  Notion ID: {data["notion_id"]}')


if __name__ == '__main__':
    main()
