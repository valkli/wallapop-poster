#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_daily_batch.py — Daily batch publisher for Wallapop.
Publishes 6-8 products from Notion, skipping those without accessible images.

Usage: python wallapop-poster/run_daily_batch.py
"""

import os
import sys
import json
import time
import random
import subprocess
import requests
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

WORKSPACE = Path(__file__).parent.parent
SCRIPT_DIR = Path(__file__).parent
NOTION_API_KEY = os.environ.get('NOTION_API_KEY', '')

HEADERS = {
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}

IMG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
    'Referer': 'https://www.google.com/',
}

MAX_PRODUCTS = 8
MIN_PRICE = 15.0
REPORT_PATH = SCRIPT_DIR / 'temp' / 'daily_report.json'


def run(cmd, timeout=60):
    """Run a subprocess command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(WORKSPACE))
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def fetch_next_product():
    """Fetch next product from Notion."""
    stdout, stderr, rc = run([sys.executable, str(SCRIPT_DIR / 'fetch_product_for_wallapop.py')], timeout=30)
    print(f'  fetch: {stdout[:100]}', flush=True)
    if stderr and 'remaining' not in stderr:
        print(f'  fetch stderr: {stderr[:200]}', flush=True)
    return stdout


def check_image_accessible(url):
    """Try to download image. Returns (ok, path_or_none)."""
    if not url:
        return False, None
    try:
        r = requests.get(url, headers=IMG_HEADERS, timeout=20, stream=True)
        if r.ok and 'image' in r.headers.get('Content-Type', ''):
            img_path = SCRIPT_DIR / 'temp' / 'product_image.jpg'
            img_path.parent.mkdir(parents=True, exist_ok=True)
            img_path.write_bytes(r.content)
            size_kb = len(r.content) // 1024
            print(f'  ✓ Image downloaded: {size_kb}KB', flush=True)
            return True, str(img_path)
        else:
            print(f'  ✗ Image failed: HTTP {r.status_code} {r.headers.get("Content-Type", "")}', flush=True)
            return False, None
    except Exception as e:
        print(f'  ✗ Image error: {e}', flush=True)
        return False, None


def mark_no_image(notion_id):
    """Mark product as NO-IMAGE-SKIP in Notion."""
    r = requests.patch(
        f'https://api.notion.com/v1/pages/{notion_id}',
        headers=HEADERS,
        json={'properties': {'Wallapop Posted': {'rich_text': [{'type': 'text', 'text': {'content': 'NO-IMAGE-SKIP'}}]}}}
    )
    if r.status_code == 200:
        print(f'  → Marked NO-IMAGE-SKIP: {notion_id[:8]}...', flush=True)
    else:
        print(f'  ✗ Failed to mark: {r.status_code}', flush=True)


def navigate_to_upload():
    """Navigate the mixmix browser to Wallapop upload page via CDP."""
    import asyncio
    async def nav():
        try:
            import websockets
            # Find first page tab
            resp = requests.get('http://127.0.0.1:18801/json', timeout=5)
            tabs = resp.json()
            ws_url = None
            for t in tabs:
                if t.get('type') == 'page':
                    ws_url = t['webSocketDebuggerUrl']
                    break
            if not ws_url:
                return False
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': 'https://es.wallapop.com/app/catalog/upload'}}))
                await asyncio.wait_for(ws.recv(), timeout=10)
            return True
        except Exception as e:
            print(f'  CDP nav error: {e}', flush=True)
            return False
    return asyncio.run(nav())


def publish_product():
    """Run publish_wallapop_cdp.py and return (success, url)."""
    stdout, stderr, rc = run([sys.executable, str(SCRIPT_DIR / 'publish_wallapop_cdp.py')], timeout=240)
    # Show stderr (debug info)
    for line in stderr.split('\n'):
        if line.strip():
            print(f'    {line}', flush=True)
    print(f'  publish output: {stdout[:200]}', flush=True)
    if stdout.startswith('OK '):
        url = stdout[3:].strip()
        return True, url
    return False, stdout


def update_notion(notion_id, url):
    """Update Notion with published URL and Wal 1 = True."""
    stdout, stderr, rc = run([sys.executable, str(SCRIPT_DIR / 'update_notion_wallapop.py'), notion_id, url], timeout=30)
    print(f'  notion update: {stdout[:100]}', flush=True)
    return rc == 0


def load_published_ids():
    """Load set of notion_ids already published today (prevents duplicates)."""
    tracker = SCRIPT_DIR / 'temp' / 'published_today.json'
    if tracker.exists():
        try:
            data = json.loads(tracker.read_text())
            if data.get('date') == datetime.now().strftime('%Y-%m-%d'):
                return set(data.get('ids', []))
        except Exception:
            pass
    return set()


def save_published_id(notion_id):
    """Append a notion_id to today's published tracker."""
    tracker = SCRIPT_DIR / 'temp' / 'published_today.json'
    ids = load_published_ids()
    ids.add(notion_id)
    tracker.write_text(json.dumps({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'ids': list(ids)
    }))


def run_cleanup(execute: bool = False) -> dict:
    """Run cleanup_wallapop.py and return parsed JSON report. Returns empty report on error."""
    empty_report = {'to_delete': [], 'bad_urls': [], 'ok': [], '_stats': {}}
    cmd = [sys.executable, str(SCRIPT_DIR / 'cleanup_wallapop.py')]
    if execute:
        cmd.append('--execute')
    try:
        stdout, stderr, rc = run(cmd, timeout=120)
        # Log stderr (cleanup progress logs)
        for line in stderr.split('\n'):
            if line.strip():
                print(f'    {line}', flush=True)
        if not stdout.strip():
            print('  ⚠ Cleanup returned no output', flush=True)
            return empty_report
        report = json.loads(stdout)
        return report
    except json.JSONDecodeError as e:
        print(f'  ⚠ Cleanup JSON parse error: {e}', flush=True)
        print(f'  Raw output: {stdout[:300]}', flush=True)
        return empty_report
    except Exception as e:
        print(f'  ⚠ Cleanup exception: {e}', flush=True)
        return empty_report


def save_report_snapshot(report: dict):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def build_report(*, published, skipped, errors, cleanup, status='running', stale_safe=False):
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'status': status,
        'stale_safe': stale_safe,
        'published': published,
        'skipped': skipped,
        'errors': errors,
        'cleanup': cleanup,
    }


def main():
    published = []
    skipped = []
    errors = []
    published_ids = load_published_ids()

    print(f'\n{"="*60}', flush=True)
    print(f'🛍️ Wallapop Daily Batch — {datetime.now().strftime("%Y-%m-%d %H:%M")}', flush=True)
    print(f'Target: {MAX_PRODUCTS} products', flush=True)
    print(f'{"="*60}\n', flush=True)

    save_report_snapshot(build_report(
        published=published,
        skipped=skipped,
        errors=errors,
        cleanup={'phase': 'starting'},
        status='running',
        stale_safe=True,
    ))

    # ── PRE-BATCH CLEANUP ─────────────────────────────────────
    print('🧹 Pre-batch cleanup (execute)...', flush=True)
    cleanup_report = run_cleanup(execute=True)
    stats = cleanup_report.get('_stats', {})
    deleted_count = stats.get('deleted', 0)
    errors_count = stats.get('errors', 0)
    bad_urls_count = len(cleanup_report.get('bad_urls', []))
    to_delete_items = cleanup_report.get('to_delete', [])
    print(
        f'  Cleanup done: {deleted_count} listings cleared, '
        f'{bad_urls_count} bad URLs (left for manual fix), '
        f'{errors_count} errors',
        flush=True
    )
    print(f'  Still ok: {len(cleanup_report.get("ok", []))} listings', flush=True)
    print('', flush=True)

    save_report_snapshot(build_report(
        published=published,
        skipped=skipped,
        errors=errors,
        cleanup={
            'pre_deleted': deleted_count,
            'pre_deleted_items': [
                {'name': d['name'][:50], 'reason': d['reason'],
                 'wallapop_url': d.get('wallapop_url', ''),
                 'notion_url': f'https://www.notion.so/kliv/{d["notion_id"].replace("-", "")}' }
                for d in to_delete_items
            ],
            'bad_urls_count': bad_urls_count,
            'post_to_delete': None,
            'post_bad_urls': None,
            'post_ok': None
        },
        status='running',
        stale_safe=True,
    ))

    attempts = 0
    max_attempts = MAX_PRODUCTS + 10  # allow extra skips

    while len(published) < MAX_PRODUCTS and attempts < max_attempts:
        attempts += 1
        print(f'\n[{len(published)+1}/{MAX_PRODUCTS}] Fetching product #{attempts}...', flush=True)

        # STEP 1: Fetch product
        fetch_result = fetch_next_product()
        if 'NO_PRODUCTS' in fetch_result:
            print('  → No more products. Stopping.', flush=True)
            break

        if not fetch_result.startswith('OK '):
            print(f'  ✗ Unexpected fetch result: {fetch_result}', flush=True)
            errors.append(f'fetch: {fetch_result}')
            continue

        # STEP 2: Read product data
        product_data_path = SCRIPT_DIR / 'temp' / 'product_data.json'
        if not product_data_path.exists():
            print('  ✗ product_data.json not found', flush=True)
            errors.append('product_data.json missing')
            continue

        with open(product_data_path, encoding='utf-8') as f:
            data = json.load(f)

        props = data['properties']
        notion_id = data['notion_id']
        name = props.get('Name', 'Unknown')
        price = props.get('Selling Price', 0)
        donde = props.get('donde', '')
        images = props.get('Image', [])

        print(f'  Product: {name[:60]}', flush=True)
        print(f'  Price: {price}€ | donde: {donde} | images: {len(images)}', flush=True)

        # Dedup check: skip if already published in this session or today
        if notion_id in published_ids:
            print(f'  → SKIP: already published today (dedup)', flush=True)
            skipped.append(f'{name[:40]} (дубль)')
            continue

        # STEP 3: Check image
        if not images:
            print('  → No images. Skipping.', flush=True)
            mark_no_image(notion_id)
            skipped.append(f'{name[:40]} (нет фото)')
            continue

        img_ok, img_path = check_image_accessible(images[0])
        if not img_ok:
            # Try second image if available
            img_ok2 = False
            if len(images) > 1:
                img_ok2, img_path = check_image_accessible(images[1])
            if not img_ok2:
                print('  → Image not accessible (403/error). Skipping.', flush=True)
                mark_no_image(notion_id)
                skipped.append(f'{name[:40]} (фото 403)')
                save_report_snapshot(build_report(
                    published=published,
                    skipped=skipped,
                    errors=errors,
                    cleanup={
                        'pre_deleted': deleted_count,
                        'pre_deleted_items': [
                            {'name': d['name'][:50], 'reason': d['reason'],
                             'wallapop_url': d.get('wallapop_url', ''),
                             'notion_url': f'https://www.notion.so/kliv/{d["notion_id"].replace("-", "")}' }
                            for d in to_delete_items
                        ],
                        'bad_urls_count': bad_urls_count,
                        'post_to_delete': None,
                        'post_bad_urls': None,
                        'post_ok': None
                    },
                    status='running',
                    stale_safe=True,
                ))
                continue

        # STEP 4: Navigate to upload form
        print('  → Navigating to Wallapop upload...', flush=True)
        navigate_to_upload()
        time.sleep(5)

        # STEP 5-6: Publish via Playwright CDP
        print('  → Publishing...', flush=True)
        success, url = publish_product()

        if success:
            print(f'  ✅ Published: {url}', flush=True)
            # STEP 7: Update Notion + dedup tracker
            update_notion(notion_id, url)
            save_published_id(notion_id)
            published_ids.add(notion_id)
            notion_url = f'https://www.notion.so/kliv/{notion_id.replace("-", "")}'
            published.append({'name': name[:50], 'price': price, 'donde': donde, 'url': url, 'notion_id': notion_id, 'notion_url': notion_url})
            save_report_snapshot(build_report(
                published=published,
                skipped=skipped,
                errors=errors,
                cleanup={
                    'pre_deleted': deleted_count,
                    'pre_deleted_items': [
                        {'name': d['name'][:50], 'reason': d['reason'],
                         'wallapop_url': d.get('wallapop_url', ''),
                         'notion_url': f'https://www.notion.so/kliv/{d["notion_id"].replace("-", "")}' }
                        for d in to_delete_items
                    ],
                    'bad_urls_count': bad_urls_count,
                    'post_to_delete': None,
                    'post_bad_urls': None,
                    'post_ok': None
                },
                status='running',
                stale_safe=True,
            ))
            # Anti-bot pause
            pause = random.randint(30, 60)
            print(f'  ⏳ Anti-bot pause: {pause}s...', flush=True)
            time.sleep(pause)
        else:
            print(f'  ✗ Publish failed: {url}', flush=True)
            errors.append(f'{name[:40]}: {url[:80]}')
            save_report_snapshot(build_report(
                published=published,
                skipped=skipped,
                errors=errors,
                cleanup={
                    'pre_deleted': deleted_count,
                    'pre_deleted_items': [
                        {'name': d['name'][:50], 'reason': d['reason'],
                         'wallapop_url': d.get('wallapop_url', ''),
                         'notion_url': f'https://www.notion.so/kliv/{d["notion_id"].replace("-", "")}' }
                        for d in to_delete_items
                    ],
                    'bad_urls_count': bad_urls_count,
                    'post_to_delete': None,
                    'post_bad_urls': None,
                    'post_ok': None
                },
                status='running',
                stale_safe=True,
            ))

    # Final report
    print(f'\n{"="*60}', flush=True)
    print(f'📊 BATCH COMPLETE: {len(published)}/{MAX_PRODUCTS} published', flush=True)
    print(f'Skipped: {len(skipped)} | Errors: {len(errors)}', flush=True)
    print(f'{"="*60}\n', flush=True)

    # ── POST-BATCH CLEANUP STATUS (dry-run) ──────────────────
    print('\n🧹 Post-batch cleanup status (dry-run)...', flush=True)
    post_cleanup = run_cleanup(execute=False)
    post_to_delete = len(post_cleanup.get('to_delete', []))
    post_bad_urls = len(post_cleanup.get('bad_urls', []))
    post_ok = len(post_cleanup.get('ok', []))
    print(
        f'  Post-batch status: {post_ok} ok, '
        f'{post_to_delete} to_delete, '
        f'{post_bad_urls} bad_urls (not acted on)',
        flush=True
    )
    print('', flush=True)

    # Save report for Telegram
    report = build_report(
        published=published,
        skipped=skipped,
        errors=errors,
        cleanup={
            'pre_deleted': deleted_count,
            'pre_deleted_items': [
                {'name': d['name'][:50], 'reason': d['reason'],
                 'wallapop_url': d.get('wallapop_url', ''),
                 'notion_url': f'https://www.notion.so/kliv/{d["notion_id"].replace("-", "")}'}
                for d in to_delete_items
            ],
            'bad_urls_count': bad_urls_count,
            'post_to_delete': post_to_delete,
            'post_bad_urls': post_bad_urls,
            'post_ok': post_ok
        },
        status='complete',
        stale_safe=True,
    )
    save_report_snapshot(report)
    print(f'Report saved: {REPORT_PATH}', flush=True)

    return report


if __name__ == '__main__':
    report = main()
    sys.exit(0 if report['published'] else 1)
