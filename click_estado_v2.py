import asyncio, json, sys
import websockets

async def click_option():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        # First click the Estado button to open it
        js_open = """(function() {
            var wallaDropdowns = document.querySelectorAll('walla-dropdown');
            var estadoDropdown = null;
            for (var d of wallaDropdowns) {
                var fa = d.querySelector('walla-floating-area');
                if (fa && fa.textContent.includes('Estado')) {
                    estadoDropdown = d;
                    break;
                }
            }
            if (!estadoDropdown) return JSON.stringify({error: 'not found'});
            
            var btn = estadoDropdown.closest('[class*="SelectInput"]');
            if (!btn) btn = estadoDropdown.parentElement;
            
            // Find button inside
            var clickTarget = estadoDropdown.previousElementSibling;
            if (clickTarget && clickTarget.tagName === 'BUTTON') {
                clickTarget.click();
                return JSON.stringify({clicked: 'prev button', text: clickTarget.textContent.trim().substring(0,50)});
            }
            
            // Try parent button
            var parentBtn = estadoDropdown.parentElement.querySelector('button');
            if (parentBtn) {
                parentBtn.click();
                return JSON.stringify({clicked: 'parent button', text: parentBtn.textContent.trim().substring(0,50)});
            }
            
            return JSON.stringify({error: 'no button found'});
        })()"""
        
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js_open, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                val = d.get('result',{}).get('result',{}).get('value')
                sys.stdout.buffer.write(f'Open: {val}\n'.encode('utf-8'))
                break
        
        await asyncio.sleep(1.5)
        
        # Now explore the floating area shadow DOM after dropdown is open
        js_explore = """(function() {
            var wallaDropdowns = document.querySelectorAll('walla-dropdown');
            var estadoDropdown = null;
            for (var d of wallaDropdowns) {
                var fa = d.querySelector('walla-floating-area');
                if (fa && fa.textContent.includes('Estado')) {
                    estadoDropdown = d;
                    break;
                }
            }
            if (!estadoDropdown) return JSON.stringify({error: 'not found'});
            
            var fa = estadoDropdown.querySelector('walla-floating-area');
            var result = {
                faText: fa ? fa.textContent.trim().substring(0,200) : 'no fa',
                faHTML: fa ? fa.innerHTML.substring(0, 500) : 'no fa'
            };
            
            if (fa && fa.shadowRoot) {
                result.shadowHTML = fa.shadowRoot.innerHTML.substring(0, 1000);
                
                // Find all clickable elements in shadow
                var clickables = fa.shadowRoot.querySelectorAll('[role=option], button, li, [class*=item], [class*=option]');
                result.clickables = [];
                clickables.forEach(function(c) {
                    result.clickables.push({
                        tag: c.tagName,
                        text: c.textContent.trim().substring(0,60),
                        role: c.getAttribute('role')
                    });
                });
            }
            
            return JSON.stringify(result);
        })()"""
        
        cmd2 = {'id':2,'method':'Runtime.evaluate','params':{'expression': js_explore, 'returnByValue': True}}
        await ws.send(json.dumps(cmd2))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 2:
                val = d.get('result',{}).get('result',{}).get('value')
                sys.stdout.buffer.write(f'Explore: {val}\n'.encode('utf-8'))
                break

asyncio.run(click_option())
