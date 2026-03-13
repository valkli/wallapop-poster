import asyncio, json, sys
import websockets

async def find():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        
        # Look at the Estado dropdown's content slot - in light DOM as slot="floating-area-content"
        js = """(function() {
            var wallaDropdowns = document.querySelectorAll('walla-dropdown');
            var estadoDropdown = null;
            for (var d of wallaDropdowns) {
                var inner = d.innerHTML;
                if (inner.includes('Estado')) {
                    estadoDropdown = d;
                    break;
                }
            }
            if (!estadoDropdown) return JSON.stringify({error: 'not found'});
            
            // Get the walla-dropdown's all children including slot content
            var items = estadoDropdown.querySelectorAll('[role=option], [class*=dropdown-item], walla-dropdown-item');
            
            // Also try getting children with slot="floating-area-content"
            var slotContent = estadoDropdown.querySelectorAll('[slot=floating-area-content]');
            
            // Try looking at the parent container for a list
            var parentContainer = estadoDropdown.closest('[class*="SelectInput"], [class*="dropdown"]');
            
            var result = {
                estadoHTML: estadoDropdown.innerHTML.substring(0, 1000),
                items: [],
                slotContentCount: slotContent.length,
                slotContent: Array.from(slotContent).map(function(s) { return s.outerHTML.substring(0,300); }),
                parentClass: parentContainer ? parentContainer.className.substring(0,100) : 'no parent'
            };
            
            items.forEach(function(item) {
                result.items.push({tag: item.tagName, text: item.textContent.trim().substring(0,60), role: item.getAttribute('role')});
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
                try:
                    parsed = json.loads(val)
                    sys.stdout.buffer.write(json.dumps(parsed, indent=2, ensure_ascii=False).encode('utf-8'))
                    sys.stdout.buffer.write(b'\n')
                except:
                    sys.stdout.buffer.write(str(val).encode('utf-8'))
                break

asyncio.run(find())
