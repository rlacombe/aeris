#!/usr/bin/env python3
"""Capture the live public BRFSS app state after its Shiny session loads."""

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
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9447
URL = "https://alaska-dph.shinyapps.io/BRFSS/"


def tab() -> dict:
    endpoint = f"http://127.0.0.1:{PORT}/json/list"
    for _ in range(90):
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                pages = json.load(response)
            for page in pages:
                if page.get("type") == "page" and page.get("url", "").startswith(URL):
                    return page
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("No BRFSS page appeared in Chrome DevTools.")


async def evaluate(ws_url: str, expression: str):
    async with websockets.connect(ws_url, max_size=30_000_000) as socket:
        await socket.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expression, "returnByValue": True, "awaitPromise": True}}))
        while True:
            response = json.loads(await socket.recv())
            if response.get("id") == 1:
                return response["result"]["result"].get("value")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    profile = f"/private/tmp/aeris-alaska-brfss-session-{int(time.time())}"
    process = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-extensions", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", URL],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        page = tab()
        # Accept the displayed agreement. The click events give Shiny time to
        # acknowledge each checkbox before the final confirmation.
        time.sleep(10)
        for box_id in ("checkbox1", "checkbox2", "checkbox3"):
            asyncio.run(evaluate(page["webSocketDebuggerUrl"], f"document.querySelector('#{box_id}').click(); true"))
            time.sleep(2)
        for _ in range(30):
            enabled = asyncio.run(evaluate(page["webSocketDebuggerUrl"], "!document.querySelector('#agree_btn').disabled"))
            if enabled:
                break
            time.sleep(1)
        else:
            raise RuntimeError("BRFSS agreement button did not enable.")
        asyncio.run(evaluate(page["webSocketDebuggerUrl"], "document.querySelector('#agree_btn').click(); true"))
        time.sleep(45)
        expression = """(() => ({
          accessed_utc: new Date().toISOString(),
          ready_state: document.readyState,
          shiny_defined: typeof Shiny !== 'undefined',
          topic_options: Array.from(document.querySelector('#SelectTopic')?.options || []).map(x => ({value:x.value,text:x.text})),
          geography_options: Array.from(document.querySelector('#StratifyGeo')?.options || []).map(x => ({value:x.value,text:x.text})),
          page_text: document.body.innerText.slice(0, 8000),
          html: document.documentElement.outerHTML
        }))()"""
        record = asyncio.run(evaluate(page["webSocketDebuggerUrl"], expression))
        html = record.pop("html")
        (OUT / "brfss_live_session.html").write_text(html, encoding="utf-8")
        (OUT / "brfss_live_session.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(record, indent=2))
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
