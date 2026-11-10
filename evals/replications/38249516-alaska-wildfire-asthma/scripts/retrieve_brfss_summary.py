#!/usr/bin/env python3
"""Retrieve public aggregate Alaska BRFSS asthma summaries through its UI.

The Alaska BRFSS portal requires acceptance of its displayed public-data
agreement. This script uses the download controls that the portal exposes
after that agreement; it does not request record-level data.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
URL = "https://alaska-dph.shinyapps.io/BRFSS/"
PORT = 9782
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def page() -> dict:
    endpoint = f"http://127.0.0.1:{PORT}/json/list"
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                pages = json.load(response)
            for candidate in pages:
                if candidate.get("type") == "page" and candidate.get("url", "").startswith(URL):
                    return candidate
        except OSError:
            pass
        time.sleep(1)
    raise RuntimeError("No Alaska BRFSS page opened.")


async def evaluate(ws_url: str, expression: str):
    async with websockets.connect(ws_url, max_size=30_000_000) as socket:
        await socket.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
        }))
        while True:
            response = json.loads(await socket.recv())
            if response.get("id") == 1:
                result = response["result"]["result"]
                if "value" not in result:
                    raise RuntimeError(json.dumps(response, indent=2))
                return result["value"]


def js(ws_url: str, expression: str):
    return asyncio.run(evaluate(ws_url, expression))


def wait_for(ws_url: str, expression: str, label: str, seconds: int = 90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if js(ws_url, expression):
            return
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {label}.")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    log = OUT / "brfss_retrieval_progress.json"
    def checkpoint(stage: str, **details) -> None:
        log.write_text(json.dumps({"stage": stage, "at": time.time(), **details}, indent=2) + "\n")
    profile = Path(f"/private/tmp/aeris-alaska-brfss-{int(time.time())}")
    process = subprocess.Popen([
        CHROME, "--headless=new", "--disable-extensions",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
        "--no-first-run", "--no-default-browser-check", URL,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        tab = page()
        ws_url = tab["webSocketDebuggerUrl"]
        checkpoint("page_open", ws_url=ws_url)
        wait_for(ws_url, "Boolean(document.querySelector('#checkbox1'))", "public agreement")
        checkpoint("agreement_visible")
        for box in ("checkbox1", "checkbox2", "checkbox3"):
            js(ws_url, f"document.querySelector('#{box}').click(); true")
            time.sleep(3)
        wait_for(ws_url, "!document.querySelector('#agree_btn').disabled", "agreement confirmation")
        js(ws_url, "document.querySelector('#agree_btn').click(); true")
        checkpoint("agreement_accepted")
        time.sleep(10)
        checkpoint("post_accept", state=js(ws_url, """(() => ({
          socket:Shiny.shinyapp?.$socket?.readyState,
          inputs:Shiny.shinyapp?.$inputValues,
          topics:Array.from(document.querySelector('#SelectTopic').options).map(x=>({value:x.value,text:x.text}))
        }))()"""))
        wait_for(ws_url, "document.querySelector('#SelectTopic').options.length > 1", "topics", seconds=180)
        state = js(ws_url, """(() => ({
          accessed_utc:new Date().toISOString(),
          topics:Array.from(document.querySelector('#SelectTopic').options).map(x=>({value:x.value,text:x.text})),
          geographies:Array.from(document.querySelector('#StratifyGeo').options).map(x=>({value:x.value,text:x.text})),
          filters:Array.from(document.querySelector('#ExploreFilter').options).map(x=>({value:x.value,text:x.text})),
          downloads:Array.from(document.querySelectorAll('a.shiny-download-link')).map(x=>({id:x.id,href:x.href,disabled:x.getAttribute('aria-disabled')}))
        }))()""")
        (OUT / "brfss_public_session.json").write_text(json.dumps(state, indent=2) + "\n")
        print(json.dumps(state, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=15)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
