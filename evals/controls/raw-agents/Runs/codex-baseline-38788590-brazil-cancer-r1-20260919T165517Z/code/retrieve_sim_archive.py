#!/usr/bin/env python3
"""Identical-request archive probe with the contract's connection-failure schedule."""
from pathlib import Path
import hashlib, json, os, time, urllib.error, urllib.request

URL = "https://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DADOS/DO2000.dbc"
OUT = Path("/output/logs/sim_archive_attempts.jsonl")
delays = [0, 5, 15, 45, 120]  # total five attempts for connection failures
only_attempt = int(os.environ.get("SIM_ARCHIVE_ATTEMPT", "0"))
for attempt, delay in enumerate(delays, start=1):
    if only_attempt and attempt != only_attempt:
        continue
    if delay:
        time.sleep(delay)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        req = urllib.request.Request(URL, method="HEAD", headers={"User-Agent": "independent-reanalysis/1.0"})
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read()
            entry = {"attempt": attempt, "url": URL, "started": started,
                     "delay_before_seconds": delay, "status": response.status,
                     "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    except Exception as exc:
        entry = {"attempt": attempt, "url": URL, "started": started,
                 "delay_before_seconds": delay, "error_type": type(exc).__name__,
                 "error": str(exc), "bytes": 0}
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    if entry.get("status") == 200:
        break
