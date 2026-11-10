"""Join official five-digit department identifiers to ADM2 polygons by centroid."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTPUT = ROOT / "data" / "derived" / "department_boundaries.geojson"
AUDIT = ROOT / "data" / "derived" / "department_boundary_join_audit.csv"


def main() -> None:
    outcomes = pd.read_csv(ROOT / "data" / "derived" / "department_covid_outcomes_2020.csv", dtype={"department_code": str})
    references = pd.read_csv(RAW / "georef_departments.csv", dtype={"id": str, "provincia_id": str})
    references["id"] = references["id"].str.zfill(5)
    source = json.loads((RAW / "argentina_adm2.geojson").read_text(encoding="utf-8"))
    polygons = [(feature, shape(feature["geometry"])) for feature in source["features"]]
    rows: list[dict] = []
    features: list[dict] = []
    for record in outcomes.to_dict(orient="records"):
        code = record["department_code"]
        reference = references.loc[references["id"].eq(code)]
        if len(reference) != 1:
            rows.append({"department_code": code, "status": "missing_or_nonunique_georef_code"})
            continue
        item = reference.iloc[0]
        point = Point(float(item["centroide_lon"]), float(item["centroide_lat"]))
        candidates = [(feature, geometry) for feature, geometry in polygons if geometry.covers(point)]
        if len(candidates) != 1:
            rows.append(
                {
                    "department_code": code,
                    "status": "ambiguous_or_missing_polygon",
                    "candidate_polygons": len(candidates),
                    "georef_name": item["nombre"],
                    "province": item["provincia_nombre"],
                }
            )
            continue
        feature, _ = candidates[0]
        properties = {
            **record,
            "georef_name": item["nombre"],
            "georef_province": item["provincia_nombre"],
            "source_boundary_shape_id": feature["properties"]["shapeID"],
            "source_boundary_name": feature["properties"]["shapeName"],
        }
        features.append({"type": "Feature", "properties": properties, "geometry": feature["geometry"]})
        rows.append({"department_code": code, "status": "matched"})
    OUTPUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(AUDIT, index=False)
    print(json.dumps({"outcomes": len(outcomes), "matched": len(features), "unmatched": len(outcomes) - len(features)}))


if __name__ == "__main__":
    main()
