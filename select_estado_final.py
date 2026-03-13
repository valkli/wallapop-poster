import asyncio, json, sys
import websockets

async def select_practically_new():
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
        
        async def mouse_click(x, y, msg_id=100):
            for ev_type in ['mousePressed', 'mouseReleased']:
                btn = 'left'
                mc = {
                    'id': msg_id,
                    'method': 'Input.dispatchMouseEvent',
                    'params': {
                        'type': ev_type,
                        'x': x, 'y': y,
                        'button': btn,
                        'buttons': 1 if ev_type == 'mousePressed' else 0,
                        'clickCount': 1,
                        'modifiers': 0,
                        'pointerType': 'mouse'
                    }
                }
                await ws.send(json.dumps(mc))
                r = await asyncio.wait_for(ws.recv(), timeout=5)
                msg_id += 1
                await asyncio.sleep(0.05)
        
        # Step 1: Make sure Estado is closed, scroll it into view
        close_js = """(function() {
            const all = document.querySelectorAll('walla-dropdown');
            let dd = null;
            for(const d of all) { if(d.innerHTML.includes('Estado')) {dd=d; break;} }
            if(!dd) return JSON.stringify({error: 'not found'});
            const btn = dd.querySelector('[role=button]');
            // Close if open
            if(btn.getAttribute('aria-expanded') === 'true') {
                btn.click();
            }
            btn.scrollIntoView({block: 'center'});
            const rect = btn.getBoundingClientRect();
            return JSON.stringify({expanded: btn.getAttribute('aria-expanded'), x: rect.x + rect.width/2, y: rect.y + rect.height/2});
        })()"""
        result = json.loads(await eval_js(close_js, 1))
        print('State before open:', result)
        await asyncio.sleep(0.5)
        
        # Step 2: Open the dropdown via CDP mouse events
        x, y = result['x'], result['y']
        # If still open, need to get fresh coords after scroll
        if result['expanded'] == 'false':
            # Good, dropdown is closed, now click to open
            await mouse_click(x, y, 200)
            await asyncio.sleep(1.5)
        
        # Check state
        state = json.loads(await eval_js("""(function() {
            const all = document.querySelectorAll('walla-dropdown');
            let dd = null;
            for(const d of all) { if(d.innerHTML.includes('Estado')) {dd=d; break;} }
            const btn = dd.querySelector('[role=button]');
            return JSON.stringify({expanded: btn.getAttribute('aria-expanded')});
        })()""", 50))
        print('After open click:', state)
        
        # Step 3: Find the options - look in the full document for dropdown items
        # The options should now be visible. Let me find all walla-dropdown-item elements
        # (they might appear in the document now that the dropdown is open)
        find_opts = """(function() {
            // Search all shadow roots recursively
            function findAll(root, selector) {
                var results = [];
                var direct = root.querySelectorAll(selector);
                direct.forEach(function(el) { results.push(el); });
                root.querySelectorAll('*').forEach(function(el) {
                    if (el.shadowRoot) {
                        findAll(el.shadowRoot, selector).forEach(function(r) { results.push(r); });
                    }
                });
                return results;
            }
            
            var items = findAll(document, 'walla-dropdown-item');
            var result = {count: items.length, items: []};
            items.forEach(function(item) {
                var sr = item.shadowRoot;
                var text = sr ? sr.textContent.trim() : item.textContent.trim();
                var rect = item.getBoundingClientRect();
                result.items.push({
                    tag: item.tagName, 
                    text: text.substring(0,60),
                    x: rect.x + rect.width/2,
                    y: rect.y + rect.height/2,
                    visible: rect.width > 0 && rect.height > 0
                });
            });
            return JSON.stringify(result);
        })()"""
        
        items_result = json.loads(await eval_js(find_opts, 60))
        print('Found items:', json.dumps(items_result, ensure_ascii=False, indent=2))
        
        # Also check body-level portals
        portal_js = """(function() {
            // Check all top-level body children for portal content
            var result = [];
            document.body.querySelectorAll('walla-dropdown-item, [class*=dropdown-item]').forEach(function(el) {
                var text = el.textContent.trim();
                var rect = el.getBoundingClientRect();
                result.push({tag: el.tagName, text: text.substring(0,60), x: rect.x + rect.width/2, y: rect.y + rect.height/2, vis: rect.height > 0});
            });
            return JSON.stringify({count: result.length, items: result.slice(0,15)});
        })()"""
        portal_result = json.loads(await eval_js(portal_js, 70))
        print('Portal items:', json.dumps(portal_result, ensure_ascii=False))

asyncio.run(select_practically_new())
