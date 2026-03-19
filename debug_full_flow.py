#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full flow debug: go through all Wallapop upload steps."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

TEMP = 'wallapop-poster/temp'
def ss(page, name): page.screenshot(path=f'{TEMP}/flow_{name}.png'); print(f'📷 {name}')

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18801')
    ctx = b.contexts[0]
    page = ctx.pages[0]
    
    # Navigate
    print('=== STEP 1: Navigate ===')
    page.goto('https://es.wallapop.com/', timeout=60000, wait_until='domcontentloaded')
    time.sleep(2)
    page.goto('https://es.wallapop.com/app/catalog/upload', timeout=60000, wait_until='domcontentloaded')
    time.sleep(5)
    print(f'URL: {page.url}')
    
    # Type selection
    print('\n=== STEP 2: Select type ===')
    page.locator('text="Algo que ya no necesito"').first.click()
    time.sleep(3)
    
    # Summary
    print('\n=== STEP 3: Fill summary ===')
    page.locator('input[name="summary"]').first.fill('Trodat Professional sello fecha oficina')
    time.sleep(1)
    
    # Continuar #1
    print('\n=== STEP 4: Continuar #1 ===')
    page.locator('button:has-text("Continuar")').first.click()
    time.sleep(3)
    
    # Upload photo
    print('\n=== STEP 5: Upload photo ===')
    page.locator('#dropAreaPreviewInput').first.set_input_files('wallapop-poster/temp/product_image.jpg')
    time.sleep(3)
    
    # Continuar #2
    print('\n=== STEP 6: Continuar #2 ===')
    conts = page.locator('button:has-text("Continuar")')
    conts.nth(1).click()
    time.sleep(4)
    
    # Category dropdown
    print('\n=== STEP 7: Open category dropdown ===')
    cat_dropdown = page.locator('text="Categoría y subcategoría"')
    cat_dropdown.first.click()
    time.sleep(3)
    ss(page, '7_dropdown_open')
    
    # Click "Artículos de escritorio" (suggested category for stamp)
    print('\n=== STEP 8: Select category ===')
    # First try the AI suggestion
    for cat in ['Artículos de escritorio', 'Manualidades', 'Otros']:
        loc = page.locator(f'text="{cat}"')
        if loc.count() > 0 and loc.first.is_visible():
            loc.first.click()
            print(f'✓ Selected category: {cat}')
            break
    
    time.sleep(4)
    ss(page, '8_category_selected')
    print(f'URL: {page.url}')
    
    # Now check what appeared
    print('\n=== STEP 9: Check new fields ===')
    items = page.evaluate("""() => {
        let r = [];
        function fi(root) {
            root.querySelectorAll('input,textarea,select').forEach(el => {
                if (el.offsetParent !== null)
                    r.push({tag:el.tagName,type:el.type||'',ph:el.placeholder||'',
                            name:el.name||el.id||el.getAttribute('formcontrolname')||'',
                            val:(el.value||'').substring(0,30)});
            });
            root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)fi(e.shadowRoot);});
        }
        fi(document);
        return r.slice(0,30);
    }""")
    print(f'Visible inputs ({len(items)}):')
    for i in items:
        print(f'  {i["tag"]} type={i["type"]} name="{i["name"]}" ph="{i["ph"][:30]}" val="{i["val"]}"')
    
    # Check buttons
    btns = page.evaluate("""() => {
        let r = [];
        function fi(root) {
            root.querySelectorAll('button').forEach(el => {
                let txt = el.textContent.trim().substring(0,40);
                if (el.offsetParent !== null && txt)
                    r.push({txt: txt, en: !el.disabled, cls: el.className.substring(0,30)});
            });
            root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot)fi(e.shadowRoot);});
        }
        fi(document);
        return r;
    }""")
    form_btns = [b for b in btns if 'walla-button' in b['cls'] or 'Upload' in b['cls'] or 'upload' in b['cls']]
    print(f'\nForm buttons ({len(form_btns)}):')
    for b in form_btns[:15]:
        print(f'  [{b["en"]}] "{b["txt"]}"')
    
    # Scroll down to see all form fields
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(1)
    ss(page, '9_scrolled_down')
    
    print('\nDone!')
