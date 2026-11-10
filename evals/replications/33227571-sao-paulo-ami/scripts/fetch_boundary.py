#!/usr/bin/env python3
"""Build the public 39-municipality Sao Paulo metropolitan boundary."""

from __future__ import annotations

import hashlib
import gzip
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import shape, mapping
from shapely.ops import unary_union


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MUNICIPALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/35/municipios"
BOUNDARY_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}?formato=application/vnd.geo+json&qualidade=minima"
RMSP_NAMES = {
    "Arujá", "Barueri", "Biritiba Mirim", "Caieiras", "Cajamar", "Carapicuíba", "Cotia", "Diadema",
    "Embu das Artes", "Embu-Guaçu", "Ferraz de Vasconcelos", "Francisco Morato", "Franco da Rocha",
    "Guararema", "Guarulhos", "Itapecerica da Serra", "Itapevi", "Itaquaquecetuba", "Jandira", "Juquitiba",
    "Mairiporã", "Mauá", "Mogi das Cruzes", "Osasco", "Pirapora do Bom Jesus", "Poá", "Ribeirão Pires",
    "Rio Grande da Serra", "Salesópolis", "Santa Isabel", "Santana de Parnaíba", "Santo André",
    "São Bernardo do Campo", "São Caetano do Sul", "São Lourenço da Serra", "São Paulo", "Suzano",
    "Taboão da Serra", "Vargem Grande Paulista",
}


def request_json(url: str) -> object:
    error = None
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0", "Accept-Encoding": "identity"})
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read()
            if payload[:2] == b"\x1f\x8b":
                payload = gzip.decompress(payload)
            return json.loads(payload)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"IBGE request failed after four attempts: {url}: {error}")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    state_municipalities = request_json(MUNICIPALITIES_URL)
    municipalities = [item for item in state_municipalities if item.get("nome") in RMSP_NAMES]
    found_names = {item["nome"] for item in municipalities}
    if len(municipalities) != 39 or found_names != RMSP_NAMES:
        raise RuntimeError(f"Could not resolve the full 39-municipality study frame; missing={sorted(RMSP_NAMES - found_names)}.")
    records = []
    geometries = []
    for municipality in municipalities:
        code = str(municipality["id"])
        cache = RAW / "boundaries" / f"{code}.geojson"
        cache.parent.mkdir(exist_ok=True)
        if cache.exists():
            boundary = json.loads(cache.read_text())
        else:
            boundary = request_json(BOUNDARY_URL.format(code=code))
            cache.write_text(json.dumps(boundary) + "\n")
        features = boundary.get("features", [])
        if len(features) != 1:
            raise RuntimeError(f"Boundary for {code} contains {len(features)} features.")
        geometries.append(shape(features[0]["geometry"]))
        records.append({"ibge_code": code, "name": municipality["nome"]})
    union = unary_union(geometries)
    document = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"name": "Sao Paulo metropolitan region", "n_municipalities": len(records)}, "geometry": mapping(union)}]}
    boundary_path = RAW / "sao_paulo_metropolitan_39.geojson"
    boundary_path.write_text(json.dumps(document) + "\n")
    (RAW / "sao_paulo_metropolitan_municipalities.json").write_text(json.dumps(records, indent=2) + "\n")
    digest = hashlib.sha256(boundary_path.read_bytes()).hexdigest()
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "municipality_source": MUNICIPALITIES_URL, "boundary_url_template": BOUNDARY_URL, "n_municipalities": len(records), "boundary_file": str(boundary_path), "sha256": digest}
    (RAW / "boundary_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
