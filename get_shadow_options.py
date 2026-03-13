import asyncio, json
import websockets

async def check():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            var wallaDropdowns = document.querySelectorAll('walla-dropdown');
            var result = {count: wallaDropdowns.length, dropdowns: []};
            wallaDropdowns.forEach(function(el, i) {
                var shadowContent = '';
                if (el.shadowRoot) {
                    shadowContent = el.shadowRoot.innerHTML.substring(0, 300);
                }
                // Get the slot content 
                var slotContent = [];
                var assigned = [];
                if (el.shadowRoot) {
                    var slots = el.shadowRoot.querySelectorAll('slot[name=dropdown-content]');
                    slots.forEach(function(slot) {
                        var nodes = slot.assignedNodes();
                        nodes.forEach(function(n) {
                            if (n.textContent) assigned.push(n.textContent.trim().substring(0,100));
                        });
                    });
                }
                result.dropdowns.push({
                    index: i,
                    class: el.className.substring(0,60),
                    childHTML: el.innerHTML.substring(0, 400),
                    shadowContent: shadowContent,
                    assignedSlotNodes: assigned
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
                import json as j
                parsed = j.loads(val)
                print(j.dumps(parsed, indent=2, ensure_ascii=False))
                break

asyncio.run(check())
