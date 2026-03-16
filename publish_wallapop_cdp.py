#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_wallapop_cdp.py — Full Wallapop publish flow via Playwright CDP.
Connects to existing Chrome on CDP port 18800, fills the Wallapop form.

Reads: temp/product_data.json
Usage: python publish_wallapop_cdp.py
Output: OK <url> | ERROR <reason>
"""

import sys
import json
import time
import re
import subprocess
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
PRODUCT_DATA = SCRIPT_DIR / 'temp' / 'product_data.json'
CDP_PORT = 18801  # mixmix profile port
CDP_URL = f'http://127.0.0.1:{CDP_PORT}'
UPLOAD_URL = 'https://es.wallapop.com/app/catalog/upload'

# Browser profile for Wallapop
CHROMIUM_PATH = r'C:\Users\Val\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe'
BROWSER_PROFILE = r'C:\Users\Val\.openclaw\browser\mixmix'


def ensure_browser():
    """Launch OpenClaw Chromium with mixmix profile if not already running on CDP port."""
    try:
        urllib.request.urlopen(f'{CDP_URL}/json/version', timeout=3)
        print('  ✅ Browser already running on CDP', file=sys.stderr)
        return True
    except Exception:
        pass
    
    print('  🚀 Launching browser (mixmix profile)...', file=sys.stderr)
    subprocess.Popen([
        CHROMIUM_PATH,
        f'--user-data-dir={BROWSER_PROFILE}',
        f'--remote-debugging-port={CDP_PORT}',
        '--no-first-run',
        'about:blank'
    ])
    
    for _ in range(10):
        time.sleep(2)
        try:
            urllib.request.urlopen(f'{CDP_URL}/json/version', timeout=3)
            print('  ✅ Browser started', file=sys.stderr)
            return True
        except Exception:
            pass
    
    print('  ❌ Failed to start browser', file=sys.stderr)
    return False


def load_product():
    with open(PRODUCT_DATA, encoding='utf-8') as f:
        return json.load(f)


def wait_and_log(page, seconds, msg=''):
    if msg:
        print(f'  ⏳ {msg} ({seconds}s)', file=sys.stderr)
    time.sleep(seconds)


def main():
    data = load_product()
    props = data['properties']
    name = props.get('Name', '')
    price = props.get('Selling Price', 0)
    cat_wallapop = props.get('Cat-Wallapop', '')
    brand = props.get('brand', '')
    model = props.get('model', '')
    condition = props.get('Condition', '')
    
    # Build a short search query for Wallapop AI
    search_query = f"{brand} {model}".strip()
    if not search_query:
        search_query = name[:60]
    
    # Build description
    desc_parts = [name]
    if brand:
        desc_parts.append(f"Marca: {brand}")
    if model:
        desc_parts.append(f"Modelo: {model}")
    desc_parts.append("Estado: prácticamente nuevo")
    desc_parts.append("Envío disponible")
    description = "\n".join(desc_parts)
    
    print(f'Product: {name[:60]}', file=sys.stderr)
    print(f'Price: {price}€ | Cat: {cat_wallapop}', file=sys.stderr)
    print(f'Search query: {search_query}', file=sys.stderr)
    
    if not ensure_browser():
        print('ERROR: Could not start browser')
        sys.exit(1)
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        
        # Find or create a Wallapop tab
        page = None
        for pg in context.pages:
            if 'wallapop.com' in pg.url:
                page = pg
                break
        
        if not page:
            page = context.new_page()
        
        # Navigate to upload form
        print('  → Navigating to upload form...', file=sys.stderr)
        page.goto(UPLOAD_URL, timeout=60000)
        
        # Wait for page to settle (SPA routing, redirects)
        wait_and_log(page, 5, 'Waiting for page to settle')
        page.wait_for_load_state('domcontentloaded', timeout=30000)
        wait_and_log(page, 3, 'DOM loaded')
        
        current_url = page.url
        print(f'  Current URL: {current_url}', file=sys.stderr)
        
        # Check if we're on the upload page (might redirect to login)
        if 'login' in current_url.lower() or 'signin' in current_url.lower():
            print('ERROR: Not logged in to Wallapop', file=sys.stderr)
            print('ERROR not_logged_in')
            return
        
        # Take initial screenshot
        page.screenshot(path=str(SCRIPT_DIR / 'temp' / 'wallapop_initial.png'))
        print('  📷 Initial screenshot saved', file=sys.stderr)
        
        # Step 1: Upload the photo first via the file input
        print('  → Injecting photo...', file=sys.stderr)
        
        # Try to find the file input
        file_input = page.query_selector('#dropAreaPreviewInput')
        if not file_input:
            file_input = page.query_selector('input[type="file"]')
        
        if file_input:
            image_path = str(SCRIPT_DIR / 'temp' / 'product_image.jpg')
            # Download image first if needed
            images = props.get('Image', [])
            if images:
                import requests
                r = requests.get(images[0], timeout=30, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
                })
                if r.ok and len(r.content) > 1000:
                    Path(image_path).write_bytes(r.content)
                    print(f'  ✓ Image downloaded: {len(r.content)//1024}KB', file=sys.stderr)
                else:
                    print('ERROR image_download_failed')
                    return
            
            file_input.set_input_files(image_path)
            wait_and_log(page, 2, 'Photo uploaded')
            print('  ✓ Photo injected via file input', file=sys.stderr)
        else:
            print('  ⚠ File input not found, trying CDP inject...', file=sys.stderr)
        
        # Step 2: Find the main search/title input and type the search query
        # Wallapop has an AI search input where you describe what you're selling
        print('  → Looking for title/search input...', file=sys.stderr)
        
        # Try common selectors for the Wallapop form
        # The form has changed over time, try multiple approaches
        selectors_to_try = [
            'input[data-testid="upload-title-input"]',
            'input[formcontrolname="title"]',
            'tsl-input-text input',
            'input[placeholder*="título"]',
            'input[placeholder*="nombre"]',
            'input[placeholder*="buscando"]',
            'input[placeholder*="artículo"]',
            'textarea[formcontrolname="description"]',
            '#title',
        ]
        
        # Take screenshot to debug
        screenshot_path = str(SCRIPT_DIR / 'temp' / 'wallapop_form.png')
        page.screenshot(path=screenshot_path)
        print(f'  📷 Screenshot saved: {screenshot_path}', file=sys.stderr)
        
        # Let's get all visible inputs
        all_inputs = page.query_selector_all('input:visible, textarea:visible')
        print(f'  Found {len(all_inputs)} visible inputs', file=sys.stderr)
        for inp in all_inputs[:10]:
            tag = inp.evaluate('el => el.tagName')
            ph = inp.evaluate('el => el.placeholder || ""')
            tp = inp.evaluate('el => el.type || ""')
            nm = inp.evaluate('el => el.name || el.id || el.getAttribute("formcontrolname") || ""')
            print(f'    {tag} type={tp} placeholder="{ph[:40]}" name="{nm}"', file=sys.stderr)
        
        # Try to find the title input
        title_input = None
        for sel in selectors_to_try:
            title_input = page.query_selector(sel)
            if title_input:
                print(f'  ✓ Found title input: {sel}', file=sys.stderr)
                break
        
        if not title_input and all_inputs:
            # Use first visible text input
            for inp in all_inputs:
                tp = inp.evaluate('el => el.type')
                if tp in ('text', ''):
                    title_input = inp
                    print('  ✓ Using first text input as title', file=sys.stderr)
                    break
        
        if title_input:
            title_input.click()
            wait_and_log(page, 0.5)
            # Type the search query for AI auto-fill
            title_text = name[:80]  # Wallapop title max ~80 chars
            title_input.fill(title_text)
            wait_and_log(page, 2, 'Title filled, waiting for AI suggestions')
            
            # Press Tab to move to next field
            title_input.press('Tab')
            wait_and_log(page, 1)
        else:
            print('  ⚠ No title input found!', file=sys.stderr)
        
        # Step 3: Find and fill description
        desc_textarea = page.query_selector('textarea[formcontrolname="description"], textarea[data-testid="upload-description-input"], textarea')
        if desc_textarea:
            desc_textarea.click()
            desc_textarea.fill(description[:650])  # Wallapop max description
            print('  ✓ Description filled', file=sys.stderr)
            wait_and_log(page, 1)
        
        # Step 4: Find and fill price
        price_input = page.query_selector('input[formcontrolname="sale_price"], input[data-testid="upload-price-input"], input[type="number"]')
        if not price_input:
            # Try finding by placeholder
            price_input = page.query_selector('input[placeholder*="recio"], input[placeholder*="€"]')
        if price_input:
            price_input.click()
            price_input.fill(str(int(price)))
            print(f'  ✓ Price set: {int(price)}€', file=sys.stderr)
            wait_and_log(page, 1)
        
        # Step 5: Set condition to "Prácticamente nuevo" (como nuevo)
        # This is usually a dropdown/select
        condition_selectors = [
            'tsl-select[formcontrolname="condition"]',
            'select[formcontrolname="condition"]',
            '[data-testid="upload-condition-select"]',
        ]
        for sel in condition_selectors:
            cond_el = page.query_selector(sel)
            if cond_el:
                cond_el.click()
                wait_and_log(page, 1)
                # Try clicking "Como nuevo" option
                option = page.query_selector('text="Como nuevo"') or page.query_selector('text="Prácticamente nuevo"')
                if option:
                    option.click()
                    print('  ✓ Condition set: Como nuevo', file=sys.stderr)
                break
        
        wait_and_log(page, 2, 'Form filled, taking screenshot')
        
        # Take another screenshot before submit
        page.screenshot(path=str(SCRIPT_DIR / 'temp' / 'wallapop_filled.png'))
        
        # Step 6: Look for publish/submit button
        submit_selectors = [
            'button[data-testid="upload-submit-button"]',
            'button[type="submit"]',
            'button:has-text("Subir")',
            'button:has-text("Publicar")',
            'button:has-text("ubir producto")',
        ]
        
        submit_btn = None
        for sel in submit_selectors:
            try:
                submit_btn = page.query_selector(sel)
                if submit_btn:
                    is_visible = submit_btn.is_visible()
                    is_enabled = submit_btn.is_enabled()
                    print(f'  Found submit: {sel} visible={is_visible} enabled={is_enabled}', file=sys.stderr)
                    if is_visible and is_enabled:
                        break
                    submit_btn = None
            except:
                pass
        
        if submit_btn:
            print('  → Clicking submit...', file=sys.stderr)
            submit_btn.click()
            
            # Wait for navigation to success page
            try:
                page.wait_for_url('**/item/**', timeout=30000)
                published_url = page.url
                print(f'  ✓ Published! URL: {published_url}', file=sys.stderr)
                print(f'OK {published_url}')
                return
            except:
                # Check if still on form (maybe error)
                wait_and_log(page, 5, 'Waiting for redirect...')
                current_url = page.url
                if '/item/' in current_url:
                    print(f'OK {current_url}')
                    return
                else:
                    page.screenshot(path=str(SCRIPT_DIR / 'temp' / 'wallapop_after_submit.png'))
                    print(f'  ⚠ Still on: {current_url}', file=sys.stderr)
                    # Maybe the URL has the item in a different format
                    print(f'MANUAL_CHECK url={current_url}')
                    return
        else:
            page.screenshot(path=str(SCRIPT_DIR / 'temp' / 'wallapop_no_submit.png'))
            print('ERROR: Submit button not found or not enabled', file=sys.stderr)
            # List all buttons for debug
            buttons = page.query_selector_all('button:visible')
            for btn in buttons[:10]:
                txt = btn.evaluate('el => el.textContent.trim().substring(0, 50)')
                print(f'    Button: "{txt}"', file=sys.stderr)
            print('ERROR submit_not_found')


if __name__ == '__main__':
    main()
