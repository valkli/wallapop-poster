import asyncio, json
import websockets

async def check():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            var listboxes = document.querySelectorAll('[role=listbox]');
            var result = {count: listboxes.length, content: []};
            listboxes.forEach(function(lb, i) {
                result.content.push({
                    index: i,
                    innerHTML: lb.innerHTML.substring(0, 500),
                    childCount: lb.children.length,
                    ariaLabel: lb.getAttribute('aria-label')
                });
            });
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

asyncio.run(check())
