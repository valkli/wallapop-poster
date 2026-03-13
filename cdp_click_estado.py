import asyncio, json, sys
import websockets

async def click():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        # Scroll the Estado button into view and get its viewport coords
        js = """(function() {
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
            btn.scrollIntoView({block: 'center'});
            return JSON.stringify({scrolled: true, expanded: btn.getAttribute('aria-expanded')});
        })()"""
        
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                print('Scroll:', json.loads(d.get('result',{}).get('result',{}).get('value','{}')))
                break
        
        await asyncio.sleep(0.5)
        
        # Get coords after scroll
        js2 = """(function() {
            const allDropdowns = document.querySelectorAll('walla-dropdown');
            let estadoDD = null;
            for (const d of allDropdowns) {
                if (d.innerHTML.includes('Estado')) { estadoDD = d; break; }
            }
            const btn = estadoDD.querySelector('[role=button]');
            const rect = btn.getBoundingClientRect();
            return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2, top: rect.top});
        })()"""
        
        cmd2 = {'id':2,'method':'Runtime.evaluate','params':{'expression': js2, 'returnByValue': True}}
        await ws.send(json.dumps(cmd2))
        coords = None
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 2:
                coords = json.loads(d.get('result',{}).get('result',{}).get('value','{}'))
                print('Coords after scroll:', coords)
                break
        
        x, y = coords['x'], coords['y']
        
        # Dispatch CDP mouse events
        for ev_type in ['mousePressed', 'mouseReleased']:
            mouse_cmd = {
                'id': 20 + ['mousePressed','mouseReleased'].index(ev_type),
                'method': 'Input.dispatchMouseEvent',
                'params': {
                    'type': ev_type,
                    'x': x,
                    'y': y,
                    'button': 'left',
                    'buttons': 1 if ev_type == 'mousePressed' else 0,
                    'clickCount': 1,
                    'modifiers': 0,
                    'pointerType': 'mouse'
                }
            }
            await ws.send(json.dumps(mouse_cmd))
            r = await asyncio.wait_for(ws.recv(), timeout=5)
            await asyncio.sleep(0.1)
        
        await asyncio.sleep(2)
        
        # Check expanded state and find options at body level
        js3 = """(function() {
            const allDropdowns = document.querySelectorAll('walla-dropdown');
            let estadoDD = null;
            for (const d of allDropdowns) {
                if (d.innerHTML.includes('Estado')) { estadoDD = d; break; }
            }
            const btn = estadoDD ? estadoDD.querySelector('[role=button]') : null;
            const expanded = btn ? btn.getAttribute('aria-expanded') : 'no btn';
            
            // Search for walla-dropdown-item in all elements OUTSIDE the form
            // They might be portaled to document body
            const bodyChildren = document.body.children;
            const portalContainers = [];
            Array.from(bodyChildren).forEach(function(el) {
                if (!el.id && el.tagName !== 'APP-ROOT' && el.tagName !== 'SCRIPT') {
                    const items = el.querySelectorAll('[role=option], walla-dropdown-item, [class*=dropdown-item]');
                    if (items.length > 0 || el.textContent.includes('nuevo') || el.textContent.includes('estado')) {
                        portalContainers.push({
                            tag: el.tagName,
                            id: el.id,
                            class: el.className.substring(0,80),
                            itemCount: items.length,
                            text: el.textContent.trim().substring(0,100)
                        });
                    }
                }
            });
            
            return JSON.stringify({expanded, portalContainers});
        })()"""
        
        cmd3 = {'id':30,'method':'Runtime.evaluate','params':{'expression': js3, 'returnByValue': True}}
        await ws.send(json.dumps(cmd3))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 30:
                val = d.get('result',{}).get('result',{}).get('value','{}')
                parsed = json.loads(val)
                sys.stdout.buffer.write(json.dumps(parsed, indent=2, ensure_ascii=False).encode('utf-8'))
                break

asyncio.run(click())
