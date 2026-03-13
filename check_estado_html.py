import asyncio, json
import websockets

async def check():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            // Find element containing Estado
            var allBtns = Array.from(document.querySelectorAll('button'));
            var estadoEl = null;
            for (var b of allBtns) {
                var txt = b.innerText || '';
                if (txt.includes('Estado')) {
                    estadoEl = b;
                    break;
                }
            }
            if (!estadoEl) return JSON.stringify({error: 'Estado button not found'});
            
            var parent = estadoEl.parentElement;
            if (parent) {
                var sibling = parent.nextElementSibling;
                return JSON.stringify({
                    parentHTML: parent.innerHTML.substring(0, 500),
                    siblingHTML: sibling ? sibling.innerHTML.substring(0, 1000) : 'no sibling'
                });
            }
            return JSON.stringify({error: 'no parent'});
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
