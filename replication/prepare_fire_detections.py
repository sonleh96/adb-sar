"""Reconstruct detection-level inputs from FIRMS MODIS Collection 6.1 CSVs.

Obtain standard/science-quality Terra + Aqua CSVs for 2017-2022 from
https://firms.modaps.eosdis.nasa.gov/download/ or its yearly country downloads.
This is a new reconstruction, not the recovered historical preparation code.
No confidence, hotspot-type, seasonal, distance, or intensity filter is applied.
FRP stays in MW; brightness and bright_t31 stay in Kelvin. Points are not resampled.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import date
import glob
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
import tempfile

REQUIRED = ("latitude", "longitude", "brightness", "acq_date", "acq_time",
            "satellite", "confidence", "version", "bright_t31", "frp")
DERIVED = ("lat", "lon", "year", "mon", "T31", "country", "gid_1")
COUNTRIES = ("CHN", "LAO", "THA", "MMR", "KHM", "IDN", "MYS")


def expand_paths(patterns):
    paths = sorted({Path(p).resolve() for pattern in patterns for p in glob.glob(pattern)})
    if not paths or any(not p.is_file() for p in paths):
        raise ValueError("Each input group must resolve to existing files")
    for pattern in patterns:
        if not glob.glob(pattern):
            raise ValueError(f"No files match {pattern}")
    return paths


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def load_regions(paths, countries, admin_ids, repair_invalid=False):
    from shapely import make_valid
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    regions, repaired = {}, []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        crs = payload.get("crs", {}).get("properties", {}).get("name", "CRS84").upper()
        if not (crs.endswith("CRS84") or crs.endswith("EPSG:4326") or crs.endswith("EPSG::4326")):
            raise ValueError(f"{path}: GADM GeoJSON must use WGS84 longitude/latitude")
        if payload.get("type") != "FeatureCollection":
            raise ValueError(f"{path}: expected a GeoJSON FeatureCollection")
        for feature in payload["features"]:
            props = feature["properties"]
            gid, country = str(props["GID_1"]), str(props["GID_0"])
            if country not in countries or (admin_ids and gid not in admin_ids):
                continue
            if gid in regions:
                raise ValueError(f"Duplicate GADM region {gid}; supply admin-1 files once")
            geometry = shape(feature["geometry"])
            if not geometry.is_valid and repair_invalid:
                fixed = make_valid(geometry)
                parts = list(fixed.geoms) if fixed.geom_type == "GeometryCollection" else [fixed]
                geometry = unary_union([p for p in parts if p.geom_type in ("Polygon", "MultiPolygon")])
                repaired.append(gid)
            if (geometry.geom_type not in ("Polygon", "MultiPolygon") or geometry.is_empty
                    or not geometry.is_valid):
                raise ValueError(f"{gid}: invalid or non-polygon geometry; repair source explicitly or pass --repair-invalid-geometries")
            west, south, east, north = geometry.bounds
            if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
                raise ValueError(f"{gid}: coordinates outside WGS84 bounds")
            regions[gid] = (country, geometry)
    if not regions:
        raise ValueError("No GADM admin-1 regions match selection")
    if admin_ids - regions.keys():
        raise ValueError(f"Unknown selected admin-1 IDs: {sorted(admin_ids - regions.keys())}")
    items = sorted(regions.items())
    return items, STRtree([item[1][1] for item in items]), sorted(repaired)


def normalize(row):
    if None in row or any(row.get(k) is None for k in REQUIRED):
        raise ValueError("Malformed row or missing required values")
    result = {key: (value or "").strip() for key, value in row.items()}
    for key, low, high in (("latitude", -90, 90), ("longitude", -180, 180),
                           ("confidence", 0, 100), ("frp", 0, math.inf),
                           ("brightness", 0, math.inf), ("bright_t31", 0, math.inf)):
        number = float(result[key])
        if not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f"Invalid {key}: {result[key]!r}")
        result[key] = number
    observed = date.fromisoformat(result["acq_date"])
    time = result["acq_time"]
    if not time.isdigit() or len(time) > 4:
        raise ValueError(f"Invalid UTC acquisition HHMM: {time!r}")
    time = time.zfill(4)
    if int(time[:2]) > 23 or int(time[2:]) > 59:
        raise ValueError(f"Invalid UTC acquisition HHMM: {time!r}")
    satellite = {"T": "Terra", "A": "Aqua", "Terra": "Terra", "Aqua": "Aqua"}.get(result["satellite"])
    if not satellite or result.get("instrument", "MODIS") != "MODIS":
        raise ValueError("Only MODIS Terra and Aqua inputs are accepted")
    if result["version"] not in ("6.1", "61"):
        raise ValueError("Use standard MODIS Collection 6.1 records; NRT/other collections rejected")
    result.update(acq_time=time, satellite=satellite, version="6.1", acq_date=observed.isoformat())
    return result, observed


def prepare(args):
    from shapely.geometry import Point

    inputs, gadm = expand_paths(args.inputs), expand_paths(args.gadm)
    start, end = date.fromisoformat(args.start_date), date.fromisoformat(args.end_date)
    if end < start:
        raise ValueError("end-date must be on or after start-date")
    output = args.output_dir.resolve()
    if output.exists():
        raise ValueError(f"Output directory already exists: {output}; choose a new directory")
    regions, tree, repaired = load_regions(gadm, set(args.countries), set(args.admin1_ids or []), args.repair_invalid_geometries)
    fields = []
    for path in inputs:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), [])
        if len(header) != len(set(header)) or not set(REQUIRED) <= set(header):
            raise ValueError(f"{path}: expected unique FIRMS columns including {REQUIRED}")
        if set(header) & set(DERIVED):
            raise ValueError(f"{path}: source columns collide with derived fields {DERIVED}")
        fields.extend(key for key in header if key not in fields)
    counts = Counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".fire-detections-", dir=output.parent) as temporary:
        stage = Path(temporary) / "result"
        stage.mkdir()
        with closing(sqlite3.connect(Path(temporary) / "index.sqlite")) as db:
            db.execute("CREATE TABLE detections (signature TEXT PRIMARY KEY)")
            db.execute("CREATE TABLE locations (lon REAL, lat REAL, gid TEXT, country TEXT, PRIMARY KEY(lon, lat))")
            with (stage / "FRP_son.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields + list(DERIVED))
                writer.writeheader()
                for path in inputs:
                    with path.open(encoding="utf-8-sig", newline="") as source:
                        for number, raw in enumerate(csv.DictReader(source), 2):
                            counts["input_rows"] += 1
                            try:
                                row, observed = normalize(raw)
                                if not start <= observed <= end:
                                    counts["outside_dates"] += 1
                                    continue
                                # Normalize missing optional columns across split archive files.
                                signature = hashlib.sha256(json.dumps(
                                    [row.get(key, "") for key in fields], separators=(",", ":")
                                ).encode()).hexdigest()
                                fresh = db.execute("INSERT OR IGNORE INTO detections VALUES (?)", (signature,)).rowcount
                                if not fresh:
                                    counts["exact_duplicates"] += 1
                                    if args.duplicates == "error":
                                        raise ValueError("Duplicate detection; use --duplicates drop-exact or keep explicitly")
                                    if args.duplicates == "drop-exact":
                                        continue
                                lon, lat = row["longitude"], row["latitude"]
                                match = db.execute("SELECT gid, country FROM locations WHERE lon=? AND lat=?", (lon, lat)).fetchone()
                                if match is None:
                                    point = Point(lon, lat)
                                    matches = sorted(int(i) for i in tree.query(point) if regions[int(i)][1][1].covers(point))
                                    if len(matches) > 1:
                                        counts["ambiguous_locations"] += 1
                                        if args.boundaries == "error":
                                            raise ValueError(f"Location {lon},{lat} overlaps multiple admin-1 units")
                                    gid, (country, _) = regions[matches[0]] if matches else ("", ("", None))
                                    match = gid, country
                                    db.execute("INSERT INTO locations VALUES (?, ?, ?, ?)", (lon, lat, gid, country))
                                gid, country = match
                                if not gid:
                                    counts["unassigned_rows"] += 1
                                    if args.unassigned == "error":
                                        raise ValueError(f"Location {lon},{lat} is outside selected GADM polygons")
                                    if args.unassigned == "drop":
                                        continue
                                label = args.myanmar_code if country == "MMR" else country
                                row.update(lat=lat, lon=lon, year=observed.year, mon=observed.month,
                                           T31=row["bright_t31"], country=label, gid_1=gid)
                                writer.writerow(row)
                                counts["output_rows"] += 1
                                counts[f"satellite_{row['satellite']}"] += 1
                            except (ValueError, TypeError) as exc:
                                raise ValueError(f"{path}:{number}: {exc}") from exc
                            if counts["input_rows"] % 10000 == 0:
                                db.commit()
            with (stage / "lon-lat-adm1.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["lon", "lat", "gid_1", "country"])
                for lon, lat, gid, country in db.execute("SELECT lon, lat, gid, country FROM locations ORDER BY lon, lat"):
                    if gid or args.unassigned == "keep":
                        writer.writerow([lon, lat, gid, args.myanmar_code if country == "MMR" else country])
                        counts["lookup_rows"] += 1
        if not counts["output_rows"]:
            raise ValueError("No detections retained; check dates and selected polygons")
        if args.write_dta:
            import pandas as pd
            frame = pd.read_csv(stage / "FRP_son.csv", dtype={"acq_time": str, "version": str}, keep_default_na=False)
            frame.to_stata(stage / "FRP_son.dta", write_index=False, version=118)
        manifest = {
            "method": "reconstructed FIRMS standard MODIS Collection 6.1 detection preparation",
            "inputs": [fingerprint(p) for p in inputs], "gadm": [fingerprint(p) for p in gadm],
            "inclusive_dates": [start.isoformat(), end.isoformat()], "countries": args.countries,
            "admin1_ids": sorted(gid for gid, _ in regions), "counts": dict(sorted(counts.items())),
            "repaired_geometry_ids": repaired,
            "policies": {"duplicates": args.duplicates, "unassigned": args.unassigned,
                         "boundaries": args.boundaries, "myanmar_country_code": args.myanmar_code,
                         "spatial_join": "WGS84 point covered by admin-1 polygon; first means lexical GID_1",
                         "confidence_or_type_filter": "none", "seasonal_or_distance_filter": "none"},
            "units": {"frp": "MW", "brightness": "K", "bright_t31": "K", "T31": "K"},
            "schema_note": "FIRMS fields retained; lat/lon, year/mon, T31, country and gid_1 added. Historical Stata schema not verified.",
            "sources": ["https://firms.modaps.eosdis.nasa.gov/download/Readme.txt",
                        "https://firms.modaps.eosdis.nasa.gov/descriptions/FIRMS_MODIS_Firehotspots.html"],
            "outputs": [fingerprint(p) | {"path": p.name} for p in sorted(stage.iterdir())],
        }
        (stage / "fire_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    return {"output_directory": str(output), "counts": dict(sorted(counts.items()))}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", required=True, help="FIRMS MODIS standard CSV paths or quoted globs")
    parser.add_argument("--gadm", nargs="+", required=True, help="GADM 4.1 admin-1 GeoJSON paths or quoted globs")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for CSVs, manifest and optional DTA")
    parser.add_argument("--start-date", default="2017-01-01")
    parser.add_argument("--end-date", default="2022-12-31", help="Inclusive UTC date")
    parser.add_argument("--countries", nargs="+", choices=COUNTRIES, default=list(COUNTRIES))
    parser.add_argument("--admin1-ids", nargs="+", help="Optional explicit subset of GADM GID_1 values")
    parser.add_argument("--myanmar-code", choices=("MYM", "MMR"), default="MYM", help="Country label only; GADM IDs remain MMR")
    parser.add_argument("--duplicates", choices=("error", "drop-exact", "keep"), default="error")
    parser.add_argument("--unassigned", choices=("error", "drop", "keep"), default="error")
    parser.add_argument("--boundaries", choices=("error", "first"), default="error", help="Policy for multiple covering polygons")
    parser.add_argument("--repair-invalid-geometries", action="store_true", help="Explicitly make invalid GADM geometries valid and retain polygonal components")
    parser.add_argument("--write-dta", action="store_true", help="Also write Stata 118; requires pandas and memory for full retained table")
    return parser


def main(argv=None):
    parser = build_parser()
    try:
        print(json.dumps(prepare(parser.parse_args(argv)), indent=2))
    except (ValueError, KeyError, OSError, ImportError, json.JSONDecodeError) as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
