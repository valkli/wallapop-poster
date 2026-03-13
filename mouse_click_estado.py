import asyncio, json, sys
import websockets

async def click():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        # Get coordinates of the Estado button
        js_coords = """(function() {
            const allDropdowns = document.querySelectorAll('walla-dropdown');
            let estadoDD = null;
            for (const d of allDropdowns) {
                if (d.innerHTML.includes('Estado')) {
                    estadoDD = d;
                    break;
                }
            }
            if (!estadoDD) return JSON.stringify({error: 'not found'});
            const btn = estadoDD.querySelector('[role=button]');
            if (!btn) return JSON.stringify({error: 'no btn'});
            const rect = btn.getBoundingClientRect();
            return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2, expanded: btn.getAttribute('aria-expanded')});
        })()"""
        
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js_coords, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        coords = None
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                val = d.get('result',{}).get('result',{}).get('value')
                coords = json.loads(val)
                print('Estado button coords:', coords)
                break
        
        if 'error' in coords:
            return
        
        # Use CDP Input.dispatchMouseEvent to click
        x = coords['x']
        y = coords['y']
        
        # Mouse moved
        for event_type in ['mouseMoved', 'mousePressed', 'mouseReleased']:
            mouse_cmd = {
                'id': 10 + ['mouseMoved', 'mousePressed', 'mouseReleased'].index(event_type),
                'method': 'Input.dispatchMouseEvent',
                'params': {
                    'type': event_type,
                    'x': x,
                    'y': y,
                    'button': 'none' if event_type == 'mouseMoved' else 'left',
                    'clickCount': 1 if event_type in ['mousePressed', 'mouseReleased'] else 0,
                    'modifiers': 0
                }
            }
            await ws.send(json.dumps(mouse_cmd))
            await asyncio.sleep(0.1)
        
        # Wait for response
        await asyncio.sleep(2)
        
        # Check if expanded
        cmd2 = {'id':20,'method':'Runtime.evaluate','params':{'expression': js_coords, 'returnByValue': True}}
        await ws.send(json.dumps(cmd2))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 20:
                val = d.get('result',{}).get('result',{}).get('value')
                print('After click:', val)
                break
        
        # Now look for option items
        await asyncio.sleep(1)
        
        js_options = """(function() {
            const allDropdowns = document.querySelectorAll('walla-dropdown');
            let estadoDD = null;
            for (const d of allDropdowns) {
                if (d.innerHTML.includes('Estado')) {
                    estadoDD = d;
                    break;
                }
            }
            if (!estadoDD) return JSON.stringify({error: 'dropdown not found'});
            
            const fa = estadoDD.querySelector('walla-floating-area');
            const contentDiv = fa ? fa.querySelector('[slot=floating-area-content]') : null;
            
            if (!contentDiv) return JSON.stringify({error: 'no content div'});
            
            // Look for items inside the content div's slot
            // The slot content contains walla-dropdown-item references
            const innerListbox = contentDiv.querySelector('[role=listbox]');
            if (!innerListbox) return JSON.stringify({error: 'no listbox', contentHTML: contentDiv.innerHTML.substring(0,300)});
            
            // Look for items in slots within the listbox
            const items = innerListbox.querySelectorAll('[role=option], walla-dropdown-item, button');
            const result = {count: items.length, items: [], listboxHTML: innerListbox.innerHTML.substring(0, 1000)};
            items.forEach(function(item) {
                result.items.push({tag: item.tagName, text: item.textContent.trim().substring(0,80), visible: item.offsetParent !== null});
            });
            return JSON.stringify(result);
        })()"""
        
        cmd3 = {'id':30,'method':'Runtime.evaluate','params':{'expression': js_options, 'returnByValue': True}}
        await ws.send(json.dumps(cmd3))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 30:
                val = d.get('result',{}).get('result',{}).get('value')
                try:
                    parsed = json.loads(val)
                    sys.stdout.buffer.write(json.dumps(parsed, indent=2, ensure_ascii=False).encode('utf-8'))
                except:
                    sys.stdout.buffer.write(str(val).encode('utf-8'))
                break

asyncio.run(click())
