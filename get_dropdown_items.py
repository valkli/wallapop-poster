import asyncio, json
import websockets

async def check():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            var items = document.querySelectorAll('walla-dropdown-item');
            var result = {count: items.length, items: []};
            items.forEach(function(el, i) {
                if (i < 30) {
                    var sr = el.shadowRoot ? el.shadowRoot.innerHTML.substring(0,200) : '';
                    result.items.push({
                        index: i,
                        outerHTML: el.outerHTML.substring(0, 300),
                        shadowRoot: sr,
                        textContent: el.textContent.trim().substring(0, 100),
                        dataValue: el.getAttribute('data-value'),
                        value: el.value
                    });
                }
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
                import json as j
                parsed = j.loads(val)
                print(j.dumps(parsed, indent=2, ensure_ascii=False))
                break

asyncio.run(check())
