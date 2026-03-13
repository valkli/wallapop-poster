import asyncio, json
import websockets

async def select_estado():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        # First, find and click the Estado button to open the dropdown
        js_open = """(function() {
            // Find the Estado button
            var selects = document.querySelectorAll('tsl-select, walla-select, [class*="StateInput"], [class*="estado"], [class*="Estado"]');
            
            // Look for button that contains "Estado" text
            var allButtons = document.querySelectorAll('[aria-haspopup="listbox"]');
            var estadoBtn = null;
            for (var b of allButtons) {
                if (b.textContent.includes('Estado') || b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('Estado')) {
                    estadoBtn = b;
                }
            }
            
            if (!estadoBtn) {
                // Try another approach - find parent generic with "Estado*" text
                var all = document.querySelectorAll('button');
                for (var b of all) {
                    var inner = b.querySelector('[class*="label"], [class*="placeholder"]');
                    if (inner && inner.textContent.trim() === 'Estado*') {
                        estadoBtn = b;
                        break;
                    }
                }
            }
            
            if (!estadoBtn) {
                return JSON.stringify({error: 'Estado button not found', buttonCount: allButtons.length});
            }
            
            estadoBtn.click();
            return JSON.stringify({clicked: true, text: estadoBtn.textContent.trim().substring(0,50)});
        })()"""
        
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js_open, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                val = d.get('result',{}).get('result',{}).get('value')
                print('Open result:', val)
                break
        
        # Wait a bit for dropdown to open
        await asyncio.sleep(1)
        
        # Now find and click "Prácticamente nuevo" option
        # Wallapop uses walla-dropdown-item or similar elements inside shadow DOM
        js_click = """(function() {
            // Get all clickable elements in the page including shadow DOM
            function findTextInShadow(root, text) {
                var found = [];
                // Check direct children
                root.querySelectorAll('*').forEach(function(el) {
                    if (el.textContent.trim() === text || el.innerText && el.innerText.trim() === text) {
                        found.push(el);
                    }
                });
                // Check shadow roots
                root.querySelectorAll('*').forEach(function(el) {
                    if (el.shadowRoot) {
                        var sub = findTextInShadow(el.shadowRoot, text);
                        found = found.concat(sub);
                    }
                });
                return found;
            }
            
            // Look for dropdown items
            var targets = ['Prácticamente nuevo', 'Pr\\u00e1cticamente nuevo', 'Practicamente nuevo'];
            var found = null;
            for (var t of targets) {
                var els = findTextInShadow(document, t);
                if (els.length > 0) {
                    found = els[0];
                    break;
                }
            }
            
            if (found) {
                found.click();
                return JSON.stringify({clicked: true, tag: found.tagName, text: found.textContent.trim()});
            }
            
            // Try walla-dropdown-items
            var allDropdownItems = document.querySelectorAll('walla-dropdown-item');
            var itemTexts = [];
            allDropdownItems.forEach(function(el) {
                itemTexts.push({tag: el.tagName, text: el.textContent.trim(), shadow: el.shadowRoot ? el.shadowRoot.textContent.trim() : ''});
            });
            
            // Also check open dropdown items more broadly
            var openListbox = document.querySelector('[role=listbox]:not([hidden])');
            var listboxHTML = openListbox ? openListbox.innerHTML.substring(0, 500) : 'no open listbox';
            
            return JSON.stringify({error: 'option not found', dropdownItems: itemTexts.slice(0,10), listboxHTML: listboxHTML});
        })()"""
        
        cmd2 = {'id':2,'method':'Runtime.evaluate','params':{'expression': js_click, 'returnByValue': True}}
        await ws.send(json.dumps(cmd2))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=15)
            d = json.loads(r)
            if d.get('id') == 2:
                val = d.get('result',{}).get('result',{}).get('value')
                print('Click result:', val)
                break

asyncio.run(select_estado())
