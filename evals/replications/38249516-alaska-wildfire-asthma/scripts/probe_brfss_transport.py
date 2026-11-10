#!/usr/bin/env python3
"""Record whether the public BRFSS portal establishes its data session."""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PORT = 9793
URL = "https://alaska-dph.shinyapps.io/BRFSS/"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def tab():
    for _ in range(12):
        try:
            pages = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2))
            return next(x for x in pages if x.get("type") == "page" and x.get("url", "").startswith(URL))
        except Exception:
            time.sleep(1)
    raise RuntimeError("Public portal did not open in time.")


async def eval_js(ws_url, expression):
    async with websockets.connect(ws_url, max_size=30_000_000) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True}}))
        while True:
            response = json.loads(await ws.recv())
            if response.get("id") == 1:
                result = response["result"]["result"]
                if "value" not in result:
                    raise RuntimeError(json.dumps(response, indent=2))
                return result["value"]


def js(ws_url, expression):
    return asyncio.run(eval_js(ws_url, expression))


def main():
    profile = f"/private/tmp/aeris-alaska-brfss-probe-{int(time.time())}"
    proc = subprocess.Popen([CHROME, "--headless=new", "--disable-extensions", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}", "--no-first-run", URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws_url = tab()["webSocketDebuggerUrl"]
        for _ in range(20):
            if js(ws_url, "Boolean(document.querySelector('#checkbox1'))"):
                break
            time.sleep(1)
        else:
            raise RuntimeError("The public agreement did not appear.")
        after_boxes = js(ws_url, """(() => {
          for (const id of ['checkbox1','checkbox2','checkbox3']) {
            const box = document.querySelector('#' + id);
            box.checked = true;
            box.dispatchEvent(new Event('input', {bubbles:true}));
            box.dispatchEvent(new Event('change', {bubbles:true}));
          }
          return {boxes:[...document.querySelectorAll('#checkbox1,#checkbox2,#checkbox3')].map(x=>x.checked), disabled:document.querySelector('#agree_btn').disabled};
        })()""")
        time.sleep(8)
        before_confirm = js(ws_url, "({boxes:[...document.querySelectorAll('#checkbox1,#checkbox2,#checkbox3')].map(x=>x.checked), disabled:document.querySelector('#agree_btn').disabled})")
        js(ws_url, "document.querySelector('#agree_btn')?.click(); true")
        time.sleep(2)
        js(ws_url, """(() => {
          Array.from(document.querySelectorAll('a[data-value]')).find(x => x.dataset.value === 'Single Indicator')?.click();
          return true;
        })()""")
        time.sleep(6)
        state = js(ws_url, """(() => ({
          accessed_utc:new Date().toISOString(),
          topic_options:Array.from(document.querySelector('#SelectTopic')?.options||[]).map(x=>({value:x.value,text:x.text})),
          shiny_defined:typeof Shiny !== 'undefined',
          shiny_inputs:Shiny.shinyapp?.$inputValues || null,
          socket_state:Shiny.shinyapp?.$socket?.readyState ?? null,
          agreement_present:Boolean(document.querySelector('#agree_btn')),
          body_tail:document.body.innerText.slice(-1000)
        }))()""")
        state["after_boxes"] = after_boxes
        state["before_confirm"] = before_confirm
        OUT.joinpath("brfss_transport_probe.json").write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps(state, indent=2))
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
