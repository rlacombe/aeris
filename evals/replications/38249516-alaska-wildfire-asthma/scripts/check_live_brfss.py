#!/usr/bin/env python3
"""Print the state of the local public BRFSS browser session."""

import asyncio
import json
import urllib.request

import websockets


async def main():
    pages = json.load(urllib.request.urlopen("http://127.0.0.1:9782/json/list"))
    page = next(x for x in pages if x.get("type") == "page" and "alaska-dph" in x.get("url", ""))
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=30_000_000) as socket:
        await socket.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": """(() => ({
                  agreement: [...document.querySelectorAll('#checkbox1,#checkbox2,#checkbox3')].map(x=>({id:x.id,checked:x.checked})),
                  agreeDisabled: document.querySelector('#agree_btn')?.disabled,
                  shiny: typeof Shiny === 'undefined' ? null : {connected: Shiny.shinyapp?.$socket?.readyState, inputs: Shiny.shinyapp?.$inputValues},
                  topics: Array.from(document.querySelector('#SelectTopic')?.options||[]).map(x=>({value:x.value,text:x.text})),
                  tabs: Array.from(document.querySelectorAll('a[data-value]')).map(x=>({id:x.id,value:x.dataset.value,text:x.innerText})),
                  text: document.body.innerText.slice(-1200)
                }))()""",
                "returnByValue": True,
            },
        }))
        while True:
            response = json.loads(await socket.recv())
            if response.get("id") == 1:
                print(json.dumps(response["result"]["result"].get("value"), indent=2))
                return


asyncio.run(main())
