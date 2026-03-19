#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step-by-step debug of Wallapop form."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

def ss(page, name): page.screenshot(path=f'wallapop-poster/temp/step_{name}.png'); print(f'📷 step_{name}.png')
def show_buttons(page, label=''):
    btns = page.evaluate("""() => {
        let r = [];
        function fi(root) {
            root.querySelectorAll('button').forEach(el => {
                if (el.offsetParent !== null)
                    r.push({txt: el.textContent.trim().substring(0,40), en: !el.disabled, cls: el.className.substring(0,30)});
            });
            root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)fi(e.shadowRoot);});
        }
        fi(document);
        return r;
    }""")
    vis = [b for b in btns if b['txt']]
    print(f'  Buttons at {label} ({len(vis)} with text):')
    for b in vis[:30]:
        print(f'    [{b["en"]}] "{b["txt"]}" cls="{b["cls"]}"')

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18801')
    ctx = b.contexts[0]
    page = ctx.pages[0]
    
    # Navigate
    print('STEP 1: Navigate')
    page.goto('https://es.wallapop.com/app/catalog/upload', timeout=60000)
    time.sleep(5)
    ss(page, '1_initial')
    print(f'URL: {page.url}')
    
    # Click "Algo que ya no necesito"
    print('\nSTEP 2: Click "Algo que ya no necesito"')
    el = page.locator('text="Algo que ya no necesito"').first
    el.click()
    time.sleep(3)
    ss(page, '2_type_clicked')
    print(f'URL: {page.url}')
    
    # Fill summary
    print('\nSTEP 3: Fill summary')
    loc = page.locator('input[name="summary"]')
    print(f'  summary input count: {loc.count()}')
    if loc.count() > 0:
        loc.first.fill('Trodat Professional sello fecha')
        print('  ✓ Filled')
        time.sleep(1)
    ss(page, '3_summary_filled')
    
    show_buttons(page, 'after-summary-fill')
    
    # Click first Continuar
    print('\nSTEP 4: Click first Continuar')
    cont_loc = page.locator('button:has-text("Continuar")')
    print(f'  Continuar count: {cont_loc.count()}')
    if cont_loc.count() > 0:
        for i in range(cont_loc.count()):
            btn = cont_loc.nth(i)
            vis = btn.is_visible()
            en = btn.is_enabled()
            txt = btn.text_content()
            print(f'    Continuar[{i}]: vis={vis} en={en} txt="{txt}"')
    
    # Click first one
    first_cont = cont_loc.first
    first_cont.click()
    print('  Clicked first Continuar')
    time.sleep(2)
    ss(page, '4a_after_cont1_2s')
    print(f'  URL: {page.url}')
    time.sleep(3)
    ss(page, '4b_after_cont1_5s')
    
    show_buttons(page, 'after-Continuar')
    
    # Try to click "Otros" or appropriate category
    print('\nSTEP 5: Click category')
    for cat in ['Otros', 'Coleccionismo', 'Electrodomésticos']:
        loc = page.locator(f'button:has-text("{cat}")')
        cnt = loc.count()
        print(f'  button "{cat}": count={cnt}')
        if cnt > 0:
            for i in range(cnt):
                btn = loc.nth(i)
                print(f'    [{i}] vis={btn.is_visible()} cls="{btn.evaluate("e => e.className.substring(0,40)")}"')
        
    # Try clicking Otros
    otros = page.locator('button:has-text("Otros")')
    if otros.count() > 0:
        otros.last.click()
        print('  Clicked "Otros"')
        time.sleep(3)
        ss(page, '5_after_category')
        print(f'  URL: {page.url}')
        show_buttons(page, 'after-category')
    else:
        print('  "Otros" not found via locator, trying JS click')
        result = page.evaluate("""() => {
            let btns = Array.from(document.querySelectorAll('button'));
            for (let btn of btns) {
                if (btn.textContent.trim() === 'Otros' && btn.offsetParent !== null) {
                    console.log('Found Otros:', btn.className);
                    btn.click();
                    return {found: true, cls: btn.className};
                }
            }
            // Also check shadow DOM
            function fi(root) {
                for (let btn of root.querySelectorAll('button')) {
                    if (btn.textContent.trim() === 'Otros' && btn.offsetParent !== null) {
                        btn.click();
                        return {found: true, shadow: true, cls: btn.className};
                    }
                }
                for (let el of root.querySelectorAll('*')) {
                    if (el.shadowRoot) { let r = fi(el.shadowRoot); if (r) return r; }
                }
                return null;
            }
            return fi(document) || {found: false};
        }""")
        print(f'  JS click result: {result}')
        time.sleep(3)
        ss(page, '5_after_js_category')
    
    print(f'\nFinal URL: {page.url}')
    print('Done! Check screenshots.')
