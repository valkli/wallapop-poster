import asyncio, json
import websockets

async def click_estado():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        # Find and inspect Estado button
        js = """(function() {
            // Find Estado dropdown
            var allElements = document.querySelectorAll('walla-select, [class*="SelectInput"], [class*="select"]');
            var result = {count: allElements.length, info: []};
            allElements.forEach(function(el, i) {
                if (i < 20) {
                    result.info.push({
                        tag: el.tagName,
                        class: el.className.substring(0, 60),
                        text: el.textContent.substring(0, 80).trim()
                    });
                }
            });
            
            // Also check shadow DOM
            var shadowHosts = [];
            document.querySelectorAll('*').forEach(function(el) {
                if (el.shadowRoot) {
                    var sContent = el.shadowRoot.querySelector('[role=listbox], [class*=option]');
                    if (sContent) {
                        shadowHosts.push({tag: el.tagName, class: el.className.substring(0,60)});
                    }
                }
            });
            result.shadowHosts = shadowHosts;
            
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

asyncio.run(click_estado())
