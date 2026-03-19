#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug shadow DOM input filling."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18801')
    ctx = b.contexts[0]
    page = ctx.pages[0]
    
    page.goto('https://es.wallapop.com/app/catalog/upload', timeout=60000)
    time.sleep(5)
    
    # Click "Algo que ya no necesito"
    el = page.locator('text="Algo que ya no necesito"').first
    el.click()
    time.sleep(3)
    print('URL:', page.url)
    
    # Scan shadow DOM for inputs
    result = page.evaluate("""() => {
        let info = [];
        function scan(root, depth) {
            if (depth > 10) return;
            root.querySelectorAll("*").forEach(el => {
                if (el.shadowRoot) {
                    let inps = el.shadowRoot.querySelectorAll("input, textarea");
                    inps.forEach(inp => {
                        info.push({host: el.tagName, name: inp.name || "", type: inp.type || "", ph: inp.placeholder || "", vis: inp.offsetParent !== null});
                    });
                    scan(el.shadowRoot, depth+1);
                }
            });
        }
        scan(document, 0);
        return info.slice(0, 20);
    }""")
    print('Shadow DOM inputs:')
    for i in result:
        print(f'  host={i["host"][:20]} name={i["name"]} type={i["type"]} ph="{i["ph"][:20]}" vis={i["vis"]}')
    
    # Try Playwright locators
    for sel in ['input[name="summary"]', 'tsl-input-text input', 'input[type="text"]:not([name="search"])']:
        loc = page.locator(sel)
        try:
            cnt = loc.count()
            print(f'locator("{sel}") count={cnt}')
            if cnt > 0:
                vis = loc.first.is_visible(timeout=2000)
                print(f'  visible={vis}')
                if vis:
                    loc.first.fill('TEST FILL')
                    print(f'  FILL OK!')
                    break
        except Exception as e:
            print(f'  error: {e}')
    
    # JS direct fill
    res = page.evaluate("""() => {
        function findAndFill(root, depth) {
            if (depth > 10) return {found: false, error: "max depth"};
            let inputs = root.querySelectorAll("input[name='summary']");
            for (let inp of inputs) {
                if (inp.offsetParent !== null) {
                    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
                    setter.call(inp, "Trodat sello fecha 50chars test");
                    inp.dispatchEvent(new InputEvent("input", {bubbles: true, data: "test"}));
                    inp.dispatchEvent(new Event("change", {bubbles: true}));
                    return {found: true, val: inp.value, host: inp.offsetParent ? inp.offsetParent.tagName : "?"};
                }
            }
            for (let el of root.querySelectorAll("*")) {
                if (el.shadowRoot) {
                    let r = findAndFill(el.shadowRoot, depth + 1);
                    if (r.found) return r;
                }
            }
            return {found: false, error: "not found"};
        }
        return findAndFill(document, 0);
    }""")
    print('JS fill result:', res)
    
    time.sleep(1)
    page.screenshot(path='wallapop-poster/temp/debug_shadow.png')
    print('Screenshot saved')
