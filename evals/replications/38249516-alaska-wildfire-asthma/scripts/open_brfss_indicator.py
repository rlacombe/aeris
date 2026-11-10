#!/usr/bin/env python3
"""Open the public BRFSS single-indicator view in the active local session."""

import asyncio
import json
import urllib.request

import websockets


async def main():
    pages = json.load(urllib.request.urlopen("http://127.0.0.1:9782/json/list"))
    page = next(x for x in pages if x.get("type") == "page" and "alaska-dph" in x.get("url", ""))
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=30_000_000) as socket:
        expression = """(() => {
          const tab = Array.from(document.querySelectorAll('a[data-value]')).find(x => x.dataset.value === 'Single Indicator');
          tab.click(); return true;
        })()"""
        await socket.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True}}))
        while True:
            response = json.loads(await socket.recv())
            if response.get("id") == 1:
                print("opened")
                return


asyncio.run(main())
