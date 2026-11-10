#!/usr/bin/env python3
"""Preflight gate for PMID 33227571 public-data reanalysis.

This program deliberately performs no download or modeling when the campaign
disk guard fails.  It is an executable record of the decision rather than a
partial analysis that could be mistaken for a fitted result.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

OUT = Path("/output")
minimum_gib = 20
free = shutil.disk_usage(OUT).free
free_gib = free / 1024**3
decision = {
    "gate": "minimum free disk before a study",
    "required_gib": minimum_gib,
    "observed_free_bytes": free,
    "observed_free_gib": round(free_gib, 2),
    "pass": free_gib >= minimum_gib,
}
(OUT / "preflight_disk_check.json").write_text(json.dumps(decision, indent=2) + "\n")
if not decision["pass"]:
    raise SystemExit("STOP: campaign disk guard failed; no public-data download or model may start.")
raise SystemExit("Disk gate passed; this frozen blocker run must not be resumed automatically.")
