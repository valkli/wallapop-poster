import asyncio, json, sys
import websockets

async def explore():
    ws_url = 'ws://127.0.0.1:18800/devtools/page/07DD84969D09DD4D5F2DCBB52F1BAFF7'
    async with websockets.connect(ws_url, max_size=10_000_000) as ws:
        js = """(function() {
            var wallaDropdowns = document.querySelectorAll('walla-dropdown');
            var result = {count: wallaDropdowns.length, info: []};
            
            wallaDropdowns.forEach(function(el, i) {
                var shadowInfo = {};
                if (el.shadowRoot) {
                    // Look in shadow root
                    var allShadowEls = el.shadowRoot.querySelectorAll('*');
                    var texts = [];
                    allShadowEls.forEach(function(s) {
                        var txt = s.textContent.trim();
                        if (txt && txt.length < 100 && txt.length > 2) texts.push(txt.substring(0,50));
                    });
                    shadowInfo = {
                        innerHTML: el.shadowRoot.innerHTML.substring(0, 500),
                        textContents: texts.slice(0, 20)
                    };
                }
                
                // Check child elements  
                var children = [];
                Array.from(el.children).forEach(function(c) {
                    var cr = c.shadowRoot;
                    children.push({
                        tag: c.tagName,
                        text: c.textContent.trim().substring(0,80),
                        hasShadow: !!cr,
                        shadowText: cr ? cr.textContent.trim().substring(0,100) : ''
                    });
                });
                
                result.info.push({
                    index: i,
                    shadowInfo: shadowInfo,
                    childrenCount: el.children.length,
                    children: children.slice(0, 10)
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
                sys.stdout.buffer.write(j.dumps(parsed, indent=2, ensure_ascii=False).encode('utf-8'))
                sys.stdout.buffer.write(b'\n')
                break

asyncio.run(explore())
