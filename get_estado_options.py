import asyncio, json
import websockets

async def get_options():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            // Find Estado dropdown
            var allButtons = document.querySelectorAll('button');
            var estadoBtn = null;
            for (var b of allButtons) {
                if (b.textContent.includes('Estado') || b.getAttribute('aria-label') && b.getAttribute('aria-label').includes('Estado')) {
                    estadoBtn = b;
                    break;
                }
            }
            
            // Find listbox options
            var listboxes = document.querySelectorAll('[role=listbox]');
            var result = {listboxCount: listboxes.length, options: []};
            listboxes.forEach(function(lb) {
                var opts = lb.querySelectorAll('[role=option]');
                opts.forEach(function(o) {
                    result.options.push(o.textContent.trim());
                });
            });
            
            // Also check for any open dropdowns
            var dropdowns = document.querySelectorAll('walla-select, .dropdown-menu, [class*=dropdown]');
            result.dropdownCount = dropdowns.length;
            
            return JSON.stringify(result);
        })()"""
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                val = d.get('result',{}).get('result',{}).get('value')
                print(val)
                break

asyncio.run(get_options())
