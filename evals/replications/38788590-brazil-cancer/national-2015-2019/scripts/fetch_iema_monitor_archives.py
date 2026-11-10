#!/usr/bin/env python3
"""Download public IEMA standardized state monitor archives after AERIS audit."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "iema"
FOLDERS = {
    "BA": "1XxgIbz4Nl4ZjvOGhTq_03O5PVIidROLj", "CE": "1tIw3Gfu-pt2B7bwZZhu8C2aK8PXFYayR",
    "DF": "1FAL3CFlKsBljcNl_9smEgTZfgIxYBgpW", "ES": "1wB4QRKtIgjLLAv3NKj11_aXxWikYVM8x",
    "GO": "1mr7D3M3Wh3KVl1kKnm6ceLFMzSH9Weud", "MG": "1WE8KWKfj8fo1IE_7YKUfjxzzCwqtAmjH",
    "PR": "1QJGHU2lyGFTEvgfX7kl4RKCdVzTdObbS", "PE": "1RvxoBTiU2_2If5N5imCqyn48YDuFj6zi",
    "RJ": "1MA1LA61CD8Twpozc3bwyDaZEKVWp9ckH", "RS": "1h3NF13_8xAk4RvhWZbVrfEAf7yn7_j0z",
    "SP": "1S225sgjyNDA-2xTm_uFDr2KxDLu5KrAW",
}


def read(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=240) as response:
        return response.read()


def discover(folder_id: str) -> tuple[str, str]:
    html = read(f"https://drive.google.com/drive/folders/{folder_id}").decode("utf-8", errors="replace")
    match = re.search(r"window\['_DRIVE_ivd'\] = '([^']+)'", html)
    if not match:
        raise RuntimeError("IEMA Google Drive folder did not expose a public file index.")
    payload = bytes(match.group(1), "utf-8").decode("unicode_escape")
    item = re.search(r'\[\[\["([A-Za-z0-9_-]{20,})",\["[A-Za-z0-9_-]{20,}"\],"([^"]+\.(?:rar|zip))"', payload)
    if not item:
        raise RuntimeError("IEMA folder did not contain a public .rar or .zip archive.")
    return item.group(1), item.group(2)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def retrieve(uf: str, folder_id: str) -> dict:
    file_id, name = discover(folder_id)
    output = RAW / f"{uf}_{name}"
    if not output.exists():
        output.write_bytes(read(f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"))
    if output.stat().st_size < 1024:
        raise RuntimeError(f"IEMA archive {uf} is implausibly small")
    return {"uf": uf, "folder_url": f"https://drive.google.com/drive/folders/{folder_id}", "file_id": file_id,
            "file_name": name, "download_url": f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
            "path": str(output), "bytes": output.stat().st_size, "sha256": digest(output)}


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    records, failures = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(retrieve, uf, folder): uf for uf, folder in FOLDERS.items()}
        for future in as_completed(futures):
            try:
                records.append(future.result())
            except Exception as exc:  # Record every source failure.
                failures.append({"uf": futures[future], "error": str(exc)})
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "provider": "Instituto de Energia e Meio Ambiente (IEMA)",
                "landing_page": "https://energiaeambiente.org.br/qualidadedoar/", "records": sorted(records, key=lambda item: item["uf"]), "failures": failures}
    (RAW / "iema_download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"archives": len(records), "failures": failures}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
