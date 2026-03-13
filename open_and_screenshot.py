import asyncio, json, sys
import websockets

async def open_estado():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        async def eval_js(js, msg_id):
            cmd = {'id': msg_id, 'method': 'Runtime.evaluate', 'params': {'expression': js, 'returnByValue': True}}
            await ws.send(json.dumps(cmd))
            while True:
                r = await asyncio.wait_for(ws.recv(), timeout=10)
                d = json.loads(r)
                if d.get('id') == msg_id:
                    return d.get('result',{}).get('result',{}).get('value')
        
        # Scroll to Estado and get fresh coords
        coords_js = """(function() {
            const all = document.querySelectorAll('walla-dropdown');
            let dd = null;
            for(const d of all) { if(d.innerHTML.includes('Estado')) {dd=d; break;} }
            if(!dd) return JSON.stringify({error: 'not found'});
            const btn = dd.querySelector('[role=button]');
            btn.scrollIntoView({block: 'center'});
            const rect = btn.getBoundingClientRect();
            return JSON.stringify({
                expanded: btn.getAttribute('aria-expanded'),
                x: Math.round(rect.x + rect.width/2),
                y: Math.round(rect.y + rect.height/2),
                rect: {top: Math.round(rect.top), left: Math.round(rect.left), width: Math.round(rect.width), height: Math.round(rect.height)}
            });
        })()"""
        result = json.loads(await eval_js(coords_js, 1))
        print('Estado coords:', result)
        await asyncio.sleep(0.5)
        
        x, y = result['x'], result['y']
        expanded_before = result['expanded']
        
        # Click the Estado button (if closed, open it; if open, close then open)
        # First ensure it's closed
        if expanded_before == 'true':
            # Need to close first - click it
            mc_close = {
                'id': 200,
                'method': 'Input.dispatchMouseEvent',
                'params': {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'buttons': 1, 'clickCount': 1, 'modifiers': 0, 'pointerType': 'mouse'}
            }
            await ws.send(json.dumps(mc_close))
            r = await asyncio.wait_for(ws.recv(), timeout=5)
            mc_close2 = dict(mc_close)
            mc_close2['id'] = 201
            mc_close2['params']['type'] = 'mouseReleased'
            mc_close2['params']['buttons'] = 0
            await ws.send(json.dumps(mc_close2))
            r = await asyncio.wait_for(ws.recv(), timeout=5)
            await asyncio.sleep(0.3)
        
        # Now open it via CDP mouse click
        mc_open = {
            'id': 210,
            'method': 'Input.dispatchMouseEvent',
            'params': {'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'buttons': 1, 'clickCount': 1, 'modifiers': 0, 'pointerType': 'mouse'}
        }
        await ws.send(json.dumps(mc_open))
        r = await asyncio.wait_for(ws.recv(), timeout=5)
        mc_open2 = dict(mc_open)
        mc_open2['id'] = 211
        mc_open2['params']['type'] = 'mouseReleased'
        mc_open2['params']['buttons'] = 0
        await ws.send(json.dumps(mc_open2))
        r = await asyncio.wait_for(ws.recv(), timeout=5)
        
        await asyncio.sleep(1)
        
        # Check expanded and look for options
        check_js = """(function() {
            const all = document.querySelectorAll('walla-dropdown');
            let dd = null;
            for(const d of all) { if(d.innerHTML.includes('Estado')) {dd=d; break;} }
            const btn = dd.querySelector('[role=button]');
            const expanded = btn.getAttribute('aria-expanded');
            
            // Look for any visible dropdown content in the page
            // Check the floating-area-content div
            const fa = dd.querySelector('walla-floating-area');
            const contentDiv = fa ? fa.querySelector('[slot=floating-area-content]') : null;
            const listbox = contentDiv ? contentDiv.querySelector('[role=listbox]') : null;
            
            // Try to find items via the Stencil framework's org-location
            // These should be in the DOM somewhere with the org-location comments
            // Let's look for them in a portal (appended to body)
            let portalItems = [];
            document.body.querySelectorAll('[class*=dropdown-item], walla-dropdown-item, [data-testid*=item], [data-testid*=option]').forEach(function(el) {
                var rect = el.getBoundingClientRect();
                portalItems.push({tag: el.tagName, text: el.textContent.trim().substring(0,50), x: rect.x + rect.width/2, y: rect.y + rect.height/2, visible: rect.height > 0});
            });
            
            // Also check for items via org-location
            // Look for elements added DYNAMICALLY to the body when dropdown opens
            const bodyEl = document.body;
            const bodyDirectChildren = Array.from(bodyEl.children).map(function(el) {
                return {tag: el.tagName, id: el.id, class: el.className.substring(0,80), innerText: el.innerText ? el.innerText.trim().substring(0,200) : ''};
            });
            
            return JSON.stringify({
                expanded: expanded,
                listboxHTML: listbox ? listbox.innerHTML.substring(0,500) : 'no listbox',
                portalItems: portalItems,
                bodyChildren: bodyDirectChildren
            });
        })()"""
        
        result2 = json.loads(await eval_js(check_js, 300))
        sys.stdout.buffer.write(json.dumps(result2, indent=2, ensure_ascii=False).encode('utf-8'))
        sys.stdout.buffer.write(b'\n')

asyncio.run(open_estado())
