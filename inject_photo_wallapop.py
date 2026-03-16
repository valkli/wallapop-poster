#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inject_photo_wallapop.py
Injects a product image into Wallapop publish form via Chrome DevTools Protocol.
Works for ANY image URL regardless of CORS (loads via Python, injects as base64).

Reads:  temp/product_data.json  (for image URL)
Downloads image to temp/product_image.jpg

Usage:
  python inject_photo_wallapop.py             (auto-discovers Wallapop tab)
  python inject_photo_wallapop.py <cdp_ws_url>

Output:
  OK files=1     — image injected successfully
  NO_IMAGE       — no image URL in product_data
  ERROR <reason> — injection failed
"""

import sys
import os
import json
import base64
import asyncio
import time
import subprocess
import urllib.request as urllib_req
import requests
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_DIR   = Path(__file__).parent
PRODUCT_DATA = SCRIPT_DIR / 'temp' / 'product_data.json'
IMAGE_FILE   = SCRIPT_DIR / 'temp' / 'product_image.jpg'
CDP_PORT     = 18801  # mixmix profile port
CDP_BASE     = f'http://127.0.0.1:{CDP_PORT}'

# Browser profile for Wallapop
CHROMIUM_PATH = r'C:\Users\Val\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe'
BROWSER_PROFILE = r'C:\Users\Val\.openclaw\browser\mixmix'


def ensure_browser():
    """Launch OpenClaw Chromium with mixmix profile if not already running."""
    try:
        urllib_req.urlopen(f'{CDP_BASE}/json/version', timeout=3)
        return True
    except Exception:
        pass
    print('  🚀 Launching browser (mixmix profile)...', file=sys.stderr)
    subprocess.Popen([
        CHROMIUM_PATH,
        f'--user-data-dir={BROWSER_PROFILE}',
        f'--remote-debugging-port={CDP_PORT}',
        '--no-first-run', 'about:blank'
    ])
    for _ in range(10):
        time.sleep(2)
        try:
            urllib_req.urlopen(f'{CDP_BASE}/json/version', timeout=3)
            return True
        except Exception:
            pass
    return False

# Wallapop file input selector (directly in main DOM, not shadow DOM)
FILE_INPUT_SELECTOR = '#dropAreaPreviewInput'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}


def download_image():
    """Download product image. Returns (path, url) or exits with NO_IMAGE."""
    if not PRODUCT_DATA.exists():
        print('ERROR product_data.json not found — run fetch_product_for_wallapop.py first')
        sys.exit(1)

    with open(PRODUCT_DATA, encoding='utf-8') as f:
        data = json.load(f)

    images = data['properties'].get('Image') or []

    if not images:
        print('NO_IMAGE')
        sys.exit(0)

    SCRIPT_DIR.joinpath('temp').mkdir(parents=True, exist_ok=True)

    for url in images:
        print(f'Trying image: {url[:80]}', file=sys.stderr)
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
            r.raise_for_status()
            content_type = r.headers.get('Content-Type', '')
            if 'image' not in content_type and len(r.content) < 1000:
                raise ValueError(f'Not an image: {content_type}')
            IMAGE_FILE.write_bytes(r.content)
            size_kb = len(r.content) // 1024
            print(f'Downloaded: {size_kb} KB → {IMAGE_FILE}', file=sys.stderr)
            return str(IMAGE_FILE), url
        except Exception as e:
            print(f'  Failed: {e}', file=sys.stderr)

    print('NO_IMAGE')
    sys.exit(0)


def get_wallapop_ws_url():
    """Find the Wallapop tab WebSocket URL via CDP /json endpoint."""
    try:
        resp = requests.get(f'{CDP_BASE}/json', timeout=5)
        targets = resp.json()
        for t in targets:
            url = t.get('url', '')
            if 'wallapop.com' in url and t.get('type') == 'page':
                return t['webSocketDebuggerUrl']
        # Fallback: try any page tab
        for t in targets:
            if t.get('type') == 'page':
                print(f'Wallapop tab not found, using: {t.get("url", "")}', file=sys.stderr)
                return t['webSocketDebuggerUrl']
        print('ERROR: No page tab found in CDP targets', file=sys.stderr)
        return None
    except Exception as e:
        print(f'ERROR: Cannot connect to CDP at {CDP_BASE}: {e}', file=sys.stderr)
        return None


def build_inject_js(img_path: str) -> str:
    """
    Build JS that injects image from base64 into Wallapop's file input.
    Uses DataTransfer API + native setter to bypass React/Angular detection.
    Wallapop input: #dropAreaPreviewInput (directly in main DOM).
    """
    data = Path(img_path).read_bytes()
    b64  = base64.b64encode(data).decode()

    # Split large base64 into chunks to avoid JS string limits
    chunk_size = 50000
    chunks = [b64[i:i+chunk_size] for i in range(0, len(b64), chunk_size)]
    chunks_js = '[' + ','.join(f'"{c}"' for c in chunks) + ']'

    js = f"""() => {{
        const chunks = {chunks_js};
        const b64 = chunks.join('');
        const byteChars = atob(b64);
        const bytes = new Uint8Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
        const blob = new Blob([bytes], {{type: 'image/jpeg'}});
        const file = new File([blob], 'product.jpg', {{type: 'image/jpeg', lastModified: Date.now()}});

        const input = document.querySelector('{FILE_INPUT_SELECTOR}');
        if (!input) return {{ok: false, error: 'input not found: {FILE_INPUT_SELECTOR}'}};

        const dt = new DataTransfer();
        dt.items.add(file);

        // Use native setter to bypass framework property descriptors
        const nativeSetter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'files').set;
        nativeSetter.call(input, dt.files);

        // Dispatch events for Angular change detection
        input.dispatchEvent(new Event('change', {{bubbles: true}}));
        input.dispatchEvent(new Event('input', {{bubbles: true}}));

        // Also try Angular-specific event dispatch
        const changeEvent = new CustomEvent('change', {{bubbles: true, detail: {{files: dt.files}}}});
        input.dispatchEvent(changeEvent);

        return {{ok: true, files: input.files.length, size: input.files[0] ? input.files[0].size : 0}};
    }}"""
    return js


async def inject_via_cdp(ws_url: str, js_fn: str):
    """Send evaluate command via CDP WebSocket."""
    try:
        import websockets
    except ImportError:
        print('ERROR: websockets not installed. Run: pip install websockets')
        sys.exit(1)

    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        cmd = {
            'id': 1,
            'method': 'Runtime.evaluate',
            'params': {
                'expression': f'({js_fn})()',
                'awaitPromise': False,
                'returnByValue': True
            }
        }
        await ws.send(json.dumps(cmd))
        while True:
            resp = await asyncio.wait_for(ws.recv(), timeout=30)
            data = json.loads(resp)
            if data.get('id') == 1:
                result = data.get('result', {}).get('result', {})
                if result.get('type') == 'object':
                    return result.get('value')
                return None


def main():
    # Get CDP WS URL
    if len(sys.argv) > 1:
        ws_url = sys.argv[1]
    else:
        ws_url = get_wallapop_ws_url()
        if not ws_url:
            print('ERROR: Could not find Wallapop tab CDP URL')
            sys.exit(1)

    print(f'CDP target: {ws_url}', file=sys.stderr)

    # Download image
    img_path, img_url = download_image()

    # Build and run injection JS
    js = build_inject_js(img_path)
    size_kb = len(js) // 1024
    print(f'Injecting {size_kb}KB JS payload...', file=sys.stderr)

    result = asyncio.run(inject_via_cdp(ws_url, js))

    if result and result.get('ok'):
        files = result.get('files', '?')
        size  = result.get('size', 0)
        print(f'OK files={files} size={size//1024}KB')
    else:
        err = result.get('error', 'unknown') if result else 'no result from CDP'
        print(f'ERROR {err}')
        sys.exit(1)


if __name__ == '__main__':
    main()
