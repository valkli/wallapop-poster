import asyncio, json, sys
import websockets

async def find():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        js = """(function() {
            // Look for walla-dropdown-item anywhere in DOM
            var items = document.querySelectorAll('walla-dropdown-item');
            var result = {itemCount: items.length, items: []};
            items.forEach(function(item, i) {
                if (i < 20) {
                    var sr = item.shadowRoot;
                    result.items.push({
                        outerHTML: item.outerHTML.substring(0, 200),
                        textContent: item.textContent.trim(),
                        shadowHTML: sr ? sr.innerHTML.substring(0, 200) : null,
                        rect: JSON.stringify(item.getBoundingClientRect()),
                        visible: item.offsetParent !== null
                    });
                }
            });
            
            // Also look at the whole body for any element with condition text
            var conditions = ['nuevo', 'buen estado', 'usado', 'roto'];
            var found = [];
            document.querySelectorAll('[role=option]').forEach(function(el) {
                found.push({text: el.textContent.trim().substring(0,60), tag: el.tagName, visible: el.offsetParent !== null});
            });
            result.allOptions = found;
            
            return JSON.stringify(result);
        })()"""
        
        cmd = {'id':1,'method':'Runtime.evaluate','params':{'expression': js, 'returnByValue': True}}
        await ws.send(json.dumps(cmd))
        while True:
            r = await asyncio.wait_for(ws.recv(), timeout=10)
            d = json.loads(r)
            if d.get('id') == 1:
                val = d.get('result',{}).get('result',{}).get('value')
                try:
                    parsed = json.loads(val)
                    sys.stdout.buffer.write(json.dumps(parsed, indent=2, ensure_ascii=False).encode('utf-8'))
                    sys.stdout.buffer.write(b'\n')
                except:
                    sys.stdout.buffer.write(str(val).encode('utf-8'))
                break

asyncio.run(find())
