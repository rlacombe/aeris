#!/usr/bin/env python3
"""Inspect the public Alaska BRFSS Shiny application through Chrome DevTools.

The program writes only an HTML snapshot and JSON inspection record. It does
not bypass the public interface or submit a restricted-data request.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websockets


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / "outputs"
APP_URL = "https://alaska-dph.shinyapps.io/BRFSS/"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DEBUG_PORT = 9227


def wait_for_debugger() -> dict:
    endpoint = f"http://127.0.0.1:{DEBUG_PORT}/json/list"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                tabs = json.load(response)
            app_tabs = [tab for tab in tabs if tab.get("url", "").startswith(APP_URL)]
            if app_tabs:
                return app_tabs[0]
            if tabs:
                return tabs[0]
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Chrome DevTools endpoint did not become available.")


async def evaluate(websocket_url: str, expression: str):
    async with websockets.connect(websocket_url, max_size=20_000_000) as socket:
        await socket.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
                }
            )
        )
        while True:
            message = json.loads(await socket.recv())
            if message.get("id") == 1:
                result = message.get("result", {}).get("result", {})
                if "value" not in result:
                    raise RuntimeError(json.dumps(message, indent=2))
                return result["value"]


def run_expression(expression: str):
    return asyncio.run(evaluate(wait_for_debugger()["webSocketDebuggerUrl"], expression))


def wait_for(expression: str, description: str, timeout_seconds: float = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if run_expression(expression):
                return
        except (OSError, websockets.WebSocketException):
            pass
        time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {description}.")


def inspect_app() -> dict:
    wait_for(
        "Boolean(document.querySelector('#SelectTopic')) && document.querySelector('#SelectTopic').options.length > 1",
        "public BRFSS topic options",
    )
    run_expression("Shiny.setInputValue('SelectTopic', 'Chronic Health Indicators', {priority: 'event'}); true")
    wait_for("document.querySelector('#SelectIndicator').options.length > 1", "public BRFSS indicator options")
    indicator_options = run_expression(
        "Array.from(document.querySelector('#SelectIndicator').options).map(x => ({value:x.value,text:x.text}))"
    )
    asthma_options = [option for option in indicator_options if "asthma" in option["text"].lower()]
    if not asthma_options:
        raise RuntimeError(f"No asthma indicator returned: {indicator_options}")
    asthma = asthma_options[0]
    run_expression(
        "Shiny.setInputValue('SelectIndicator', " + json.dumps(asthma["value"]) + ", {priority: 'event'}); true"
    )
    run_expression("Shiny.setInputValue('StratifyGeo', '16', {priority: 'event'}); true")
    wait_for(
        "document.querySelector('#StratifyGeoLevel').options.length >= 10", "public BHS geographic levels"
    )
    return {
        "accessed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "url": APP_URL,
        "snapshot": run_expression("document.documentElement.outerHTML"),
        "topic_options": run_expression(
            "Array.from(document.querySelector('#SelectTopic').options).map(x => ({value:x.value,text:x.text}))"
        ),
        "indicator_options": indicator_options,
        "selected_asthma_indicator": asthma,
        "geographic_classifications": run_expression(
            "Array.from(document.querySelector('#StratifyGeo').options).map(x => ({value:x.value,text:x.text}))"
        ),
        "bhs_levels": run_expression(
            "Array.from(document.querySelector('#StratifyGeoLevel').options).map(x => ({value:x.value,text:x.text}))"
        ),
    }


def main() -> None:
    OUTPUTS.mkdir(exist_ok=True)
    profile = "/private/tmp/aeris-alaska-brfss-chrome-profile"
    process = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            APP_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        record = inspect_app()
        snapshot = record.pop("snapshot")
        (OUTPUTS / "brfss_app_snapshot.html").write_text(snapshot, encoding="utf-8")
        (OUTPUTS / "brfss_app_inspection.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(record, indent=2))
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    main()
