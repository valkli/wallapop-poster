import asyncio, json, sys
import websockets

async def find_inputs():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            var inputs = document.querySelectorAll('input[type=file]');
            var result = [];
            inputs.forEach(function(inp, i) {
                result.push({
                    index: i,
                    id: inp.id,
                    name: inp.name,
                    className: inp.className.substring(0,100),
                    accept: inp.accept,
                    parentTag: inp.parentElement ? inp.parentElement.tagName : null,
                    parentClass: inp.parentElement ? inp.parentElement.className.substring(0,80) : null
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

asyncio.run(find_inputs())
