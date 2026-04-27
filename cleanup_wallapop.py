#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanup_wallapop.py — Audit and clean up Wallapop-published listings in Notion.

Queries BOTH Notion DBs for products where `Wallapop Posted` is NOT empty.
For each, checks if the listing should still exist on Wallapop:
  - Selling Price > 15
  - donde = "magazin" or "sklad"
  - Page NOT archived/in_trash
  - Sold checkbox is NOT True
  - In Stock = False (still designated for online)

Flags products with bad URLs (catalog/published) but does NOT reset them.
Bad URLs are left for manual correction by the user.

Usage:
    python cleanup_wallapop.py           # Dry-run: print JSON report
    python cleanup_wallapop.py --execute # Execute: clear Notion fields for to_delete only

Output (JSON to stdout):
  {
    "to_delete": [...],   # No longer meet conditions → clear Wallapop Posted + Wal 1 in Notion
    "bad_urls": [...],    # Have catalog/published URL, left as-is (user will fix manually)
    "ok": [...]           # Still valid
  }
"""

import sys
import os
import json
import time
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

WORKSPACE = Path(__file__).parent.parent
SCRIPT_DIR = Path(__file__).parent

NOTION_API_KEY = os.getenv('NOTION_API_KEY', '')
HEADERS = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

# Notion database IDs
DB_GANGABOX = '2bd12f742f9e8198bfb3dce06af14f58'   # Product_Variants_GangaBox
DB_VARIANTS = '27f12f742f9e81648959ee3d597c4e7e'   # Product_Variants

# Valid donde values
VALID_DONDE = {'magazin', 'sklad'}
MIN_PRICE = 15.0


def log(msg):
    print(f'  {msg}', file=sys.stderr, flush=True)


def get_rich_text(prop) -> str:
    """Extract plain text from a Notion rich_text property."""
    if not prop:
        return ''
    items = prop.get('rich_text', [])
    return ''.join(i.get('plain_text', '') for i in items)


def get_number(prop) -> float:
    """Extract number value from a Notion number property."""
    if not prop:
        return 0.0
    val = prop.get('number')
    return float(val) if val is not None else 0.0


def get_checkbox(prop) -> bool:
    """Extract boolean from a Notion checkbox property."""
    if not prop:
        return False
    return bool(prop.get('checkbox', False))


def get_select(prop) -> str:
    """Extract selected value from a Notion select property."""
    if not prop:
        return ''
    sel = prop.get('select')
    return sel.get('name', '') if sel else ''


def get_multi_select(prop) -> list:
    """Extract list of values from a Notion multi_select property."""
    if not prop:
        return []
    return [s.get('name', '') for s in prop.get('multi_select', [])]


def get_title(prop) -> str:
    """Extract title text from a Notion title property."""
    if not prop:
        return ''
    items = prop.get('title', [])
    return ''.join(i.get('plain_text', '') for i in items)


def query_db_published(db_id: str) -> list:
    """
    Query a Notion DB for pages where `Wallapop Posted` is NOT empty.
    Returns list of raw page objects.
    """
    url = f'https://api.notion.com/v1/databases/{db_id}/query'
    pages = []
    start_cursor = None

    while True:
        body = {
            'filter': {
                'property': 'Wallapop Posted',
                'rich_text': {'is_not_empty': True}
            },
            'page_size': 100
        }
        if start_cursor:
            body['start_cursor'] = start_cursor

        try:
            r = requests.post(url, headers=HEADERS, json=body, timeout=30)
            if r.status_code != 200:
                log(f'  DB query error {db_id}: {r.status_code} {r.text[:200]}')
                break
            data = r.json()
            pages.extend(data.get('results', []))
            if not data.get('has_more'):
                break
            start_cursor = data.get('next_cursor')
        except Exception as e:
            log(f'  DB query exception {db_id}: {e}')
            break

    return pages


def classify_page(page: dict) -> dict:
    """
    Given a Notion page, classify it as to_delete, bad_url, or ok.
    Returns: {'status': 'to_delete'|'bad_url'|'ok', 'reason': str}
    """
    props = page.get('properties', {})
    archived = page.get('archived', False)
    in_trash = page.get('in_trash', False)

    wallapop_url = get_rich_text(props.get('Wallapop Posted'))
    name = (get_title(props.get('Name')) or
            get_title(props.get('name')) or
            get_rich_text(props.get('Name')) or
            'Unknown')
    price = get_number(props.get('Selling Price'))
    donde = get_select(props.get('donde'))
    sold = get_checkbox(props.get('Sold'))
    in_stock = get_checkbox(props.get('In Stock'))

    notion_id = page.get('id', '')

    # 1. Bad URL check (must come BEFORE other checks so we can flag separately)
    if 'catalog/published' in wallapop_url or (
        'catalog' in wallapop_url and '/item/' not in wallapop_url
    ):
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'bad_url',
            'reason': 'catalog_url'
        }

    # 2. Archived / deleted
    if archived or in_trash:
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'to_delete',
            'reason': 'archived_or_trash'
        }

    # 3. Sold
    if sold:
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'to_delete',
            'reason': 'sold'
        }

    # 4. Price too low
    if price <= MIN_PRICE:
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'to_delete',
            'reason': f'price_too_low ({price})'
        }

    # 5. donde changed (not magazin/sklad)
    if donde and donde.lower() not in VALID_DONDE:
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'to_delete',
            'reason': f'donde_changed ({donde})'
        }

    # 6. In Stock = True means the item is back in physical stock (not online)
    if in_stock:
        return {
            'notion_id': notion_id,
            'name': name,
            'wallapop_url': wallapop_url,
            'status': 'to_delete',
            'reason': 'in_stock_true'
        }

    # All checks passed — listing is still valid
    return {
        'notion_id': notion_id,
        'name': name,
        'wallapop_url': wallapop_url,
        'status': 'ok',
        'reason': ''
    }


def clear_notion_wallapop_fields(notion_id: str, clear_wal1: bool = True) -> bool:
    """Clear `Wallapop Posted` and optionally `Wal 1` for a Notion page."""
    props_update = {
        'Wallapop Posted': {'rich_text': []}
    }
    if clear_wal1:
        props_update['Wal 1'] = {'checkbox': False}

    try:
        r = requests.patch(
            f'https://api.notion.com/v1/pages/{notion_id}',
            headers=HEADERS,
            json={'properties': props_update},
            timeout=30
        )
        if r.status_code == 200:
            return True
        else:
            log(f'  Notion update error {notion_id}: {r.status_code} {r.text[:200]}')
            return False
    except Exception as e:
        log(f'  Notion update exception {notion_id}: {e}')
        return False


def build_report(pages: list) -> dict:
    """Classify all pages and build the report dict."""
    report = {'to_delete': [], 'bad_urls': [], 'ok': []}
    for page in pages:
        classified = classify_page(page)
        status = classified.pop('status')
        reason = classified.pop('reason', '')
        if status == 'to_delete':
            classified['reason'] = reason
            report['to_delete'].append(classified)
        elif status == 'bad_url':
            report['bad_urls'].append(classified)
        else:
            report['ok'].append({'notion_id': classified['notion_id'], 'name': classified['name']})
    return report


def execute_cleanup(report: dict) -> dict:
    """
    Execute the cleanup:
    - to_delete → clear Wallapop Posted + Wal 1 in Notion
    - bad_urls  → left as-is (user fixes manually)
    Returns stats dict.
    """
    stats = {'deleted': 0, 'bad_url_reset': 0, 'errors': 0}

    for item in report['to_delete']:
        nid = item['notion_id']
        name = item['name'][:40]
        log(f'  🗑 Clearing: {name} ({item.get("reason", "")})')
        ok = clear_notion_wallapop_fields(nid, clear_wal1=True)
        if ok:
            stats['deleted'] += 1
            log(f'    ✓ Cleared (to_delete): {nid[:8]}...')
        else:
            stats['errors'] += 1
        time.sleep(0.3)  # Rate limit friendliness

    if report['bad_urls']:
        log(f'  ℹ️ {len(report["bad_urls"])} bad URLs left as-is (manual fix)')

    return stats


def main():
    execute = '--execute' in sys.argv

    log(f'🧹 Wallapop Cleanup — {"EXECUTE" if execute else "DRY RUN"}')
    log(f'  Querying DB1 (GangaBox): {DB_GANGABOX[:8]}...')
    pages_gb = query_db_published(DB_GANGABOX)
    log(f'  Found {len(pages_gb)} published in GangaBox')

    log(f'  Querying DB2 (Variants): {DB_VARIANTS[:8]}...')
    pages_v = query_db_published(DB_VARIANTS)
    log(f'  Found {len(pages_v)} published in Variants')

    all_pages = pages_gb + pages_v
    log(f'  Total: {len(all_pages)} published listings')

    report = build_report(all_pages)

    log(f'  → to_delete: {len(report["to_delete"])} | bad_urls: {len(report["bad_urls"])} | ok: {len(report["ok"])}')

    if execute and (report['to_delete'] or report['bad_urls']):
        log('  🔧 Executing cleanup...')
        stats = execute_cleanup(report)
        report['_stats'] = stats
        log(f'  ✅ Done: deleted={stats["deleted"]} bad_url_reset={stats["bad_url_reset"]} errors={stats["errors"]}')
    elif execute:
        log('  ✅ Nothing to clean up.')
        report['_stats'] = {'deleted': 0, 'bad_url_reset': 0, 'errors': 0}

    # Output JSON report to stdout (main output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
