#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: navigate to Wallapop upload and list all inputs."""
import sys, json, time, asyncio, requests
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

CDP_URL = 'http://127.0.0.1:18801'

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
    page = context.pages[0]
    
    # Navigate
    page.goto('https://es.wallapop.com/app/catalog/upload', timeout=60000)
    time.sleep(5)
    page.wait_for_load_state('domcontentloaded')
    time.sleep(3)
    print(f'URL: {page.url}')
    
    # Click "Algo que ya no necesito"
    try:
        el = page.locator('text="Algo que ya no necesito"').first
        el.click()
        print('Clicked "Algo que ya no necesito"')
        time.sleep(3)
    except Exception as e:
        print(f'Click failed: {e}')
    
    print(f'URL after click: {page.url}')
    
    # List ALL inputs (including shadow DOM)
    js = """() => {
        let all = [];
        function fi(root) {
            root.querySelectorAll('input, textarea, button, [contenteditable]').forEach(el => {
                all.push({
                    tag: el.tagName,
                    type: el.type || '',
                    ph: el.placeholder || '',
                    name: el.name || el.id || el.getAttribute('formcontrolname') || '',
                    val: (el.value || '').substring(0, 30),
                    txt: (el.textContent || '').trim().substring(0, 30),
                    vis: el.offsetParent !== null,
                    cls: (el.className || '').substring(0, 40)
                });
            });
            root.querySelectorAll('*').forEach(el => {
                if (el.shadowRoot) fi(el.shadowRoot);
            });
        }
        fi(document);
        return all.slice(0, 50);
    }"""
    
    items = page.evaluate(js)
    print(f'\nAll inputs ({len(items)}):')
    for i in items:
        print(f'  {i["tag"]} type={i["type"]} ph="{i["ph"][:30]}" name="{i["name"][:20]}" vis={i["vis"]} val="{i["val"][:20]}" txt="{i["txt"][:20]}"')
    
    page.screenshot(path='wallapop-poster/temp/debug_after_click.png')
    print('\nScreenshot saved: debug_after_click.png')
