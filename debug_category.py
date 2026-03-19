#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug: Navigate form to category step and explore the dropdown."""
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from playwright.sync_api import sync_playwright

def ss(page, name): page.screenshot(path=f'wallapop-poster/temp/cat_{name}.png'); print(f'📷 cat_{name}')

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp('http://127.0.0.1:18801')
    ctx = b.contexts[0]
    page = ctx.pages[0]
    
    # Navigate
    page.goto('https://es.wallapop.com/app/catalog/upload', timeout=60000)
    time.sleep(5)
    
    # Click "Algo que ya no necesito"
    page.locator('text="Algo que ya no necesito"').first.click()
    time.sleep(3)
    
    # Fill summary
    page.locator('input[name="summary"]').first.fill('Trodat Professional sello fecha oficina')
    time.sleep(1)
    
    # Click Continuar #1
    page.locator('button:has-text("Continuar")').first.click()
    time.sleep(3)
    
    # Upload photo
    page.locator('#dropAreaPreviewInput').first.set_input_files('wallapop-poster/temp/product_image.jpg')
    time.sleep(3)
    
    # Click Continuar #2
    conts = page.locator('button:has-text("Continuar")')
    conts.nth(1).click()
    time.sleep(4)
    ss(page, '1_category_step')
    
    # Find and click the category dropdown
    print('\n--- Looking for category dropdown ---')
    
    # Check for tsl-select, tsl-dropdown, or similar
    dropdowns = page.evaluate("""() => {
        let r = [];
        function fi(root) {
            root.querySelectorAll('tsl-select, tsl-dropdown, select, [role="combobox"], [role="listbox"], [class*="dropdown"], [class*="select"]').forEach(el => {
                r.push({tag: el.tagName, cls: el.className.substring(0,50), role: el.getAttribute('role')||'', 
                         text: el.textContent.trim().substring(0,60), vis: el.offsetParent !== null});
            });
            root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot) fi(e.shadowRoot);});
        }
        fi(document);
        return r.slice(0,20);
    }""")
    print(f'Dropdowns found: {len(dropdowns)}')
    for d in dropdowns:
        print(f'  {d["tag"]} cls="{d["cls"][:40]}" role="{d["role"]}" vis={d["vis"]} text="{d["text"][:40]}"')
    
    # Try clicking on the category dropdown area
    # Look for "Categoría y subcategoría" text
    cat_area = page.locator('text="Categoría y subcategoría"')
    print(f'\n"Categoría y subcategoría" count: {cat_area.count()}')
    if cat_area.count() > 0:
        cat_area.first.click()
        time.sleep(2)
        ss(page, '2_dropdown_clicked')
        
        # Now check what options appeared
        options = page.evaluate("""() => {
            let r = [];
            function fi(root) {
                root.querySelectorAll('[role="option"], [role="menuitem"], li[class*="option"], div[class*="option"], tsl-option, [class*="suggestion"], [class*="tree-item"]').forEach(el => {
                    if (el.offsetParent !== null)
                        r.push({tag: el.tagName, text: el.textContent.trim().substring(0,50), cls: el.className.substring(0,40)});
                });
                root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot) fi(e.shadowRoot);});
            }
            fi(document);
            return r.slice(0,30);
        }""")
        print(f'\nOptions found: {len(options)}')
        for o in options:
            print(f'  {o["tag"]} cls="{o["cls"][:30]}" text="{o["text"][:40]}"')
    
    # Also try clicking on the UUID input
    uuid_input = page.evaluate("""() => {
        let inputs = document.querySelectorAll('input[type="text"]');
        for (let inp of inputs) {
            if (inp.name && inp.name.match(/^[0-9a-f]{8}-/)) {
                return {name: inp.name, ph: inp.placeholder, vis: inp.offsetParent !== null};
            }
        }
        return null;
    }""")
    print(f'\nUUID input: {uuid_input}')
    
    if uuid_input and uuid_input['vis']:
        loc = page.locator(f'input[name="{uuid_input["name"]}"]')
        loc.first.click()
        time.sleep(2)
        ss(page, '3_uuid_input_clicked')
        
        # Check if dropdown opened
        options2 = page.evaluate("""() => {
            let r = [];
            function fi(root) {
                root.querySelectorAll('[role="option"], [class*="suggestion"], [class*="tree-item"], li').forEach(el => {
                    if (el.offsetParent !== null && el.textContent.trim())
                        r.push({text: el.textContent.trim().substring(0,50)});
                });
                root.querySelectorAll('*').forEach(e=>{if(e.shadowRoot) fi(e.shadowRoot);});
            }
            fi(document);
            return r.slice(0,20);
        }""")
        print(f'\nOptions after UUID click: {len(options2)}')
        for o in options2[:15]:
            print(f'  "{o["text"][:40]}"')
    
    print('\nDone!')
