"""Extract historical MODIS FRP or optional FIRMS T21 country summaries.

MODIS logic ports ``docs/analysis/frp.ipynb`` cells 13-14 (one-based).
FIRMS T21 logic ports ``process_datasets.ipynb`` cell 20. T21 brightness
temperature and MODIS fire radiative power are separate products and outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .common import init_ee, month_windows


MODIS_COLLECTION = "MODIS/061/MOD14A1"
FIRMS_COLLECTION = "FIRMS"
FRP_MIN_REDUCERS = {"historical": "max", "corrected": "min"}


def fire_pixel_is_valid(fire_mask: int, qa: int) -> bool:
    """Return the pure-Python equivalent of the historical MOD14A1 masks."""

    return (int(fire_mask) & 15) >= 7 and (int(qa) & 3) <= 2


def scale_frp(value: float) -> float:
    """Apply the MOD14A1 MaxFRP 0.1 MW scale factor."""

    return float(value) * 0.1


def frp_min_reducer(temporal_mode: str) -> str:
    """Name the reducer used for the output band historically called min."""

    try:
        return FRP_MIN_REDUCERS[temporal_mode]
    except KeyError as exc:
        raise ValueError("temporal_mode must be 'historical' or 'corrected'") from exc


def _load_regions(path: Path, id_column: str) -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"GeoJSON does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid GeoJSON: {path}: {exc}") from exc
    if not isinstance(payload, Mapping) or payload.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON must be a FeatureCollection")
    crs = payload.get("crs")
    if crs is not None:
        crs_name = str((crs.get("properties") or {}).get("name", "")).upper()
        if not (crs_name.endswith("EPSG::4326") or crs_name.endswith("EPSG:4326")
                or crs_name.endswith("CRS84")):
            raise ValueError("GeoJSON must use RFC 7946 WGS84 coordinates or declare EPSG:4326")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("GeoJSON FeatureCollection must contain at least one feature")
    regions: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, feature in enumerate(features):
        if not isinstance(feature, Mapping) or feature.get("type") != "Feature":
            raise ValueError(f"feature {index} is not a GeoJSON Feature")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, Mapping) or id_column not in properties:
            raise ValueError(f"feature {index} is missing ID property {id_column!r}")
        raw_region_id = properties[id_column]
        if raw_region_id is None:
            raise ValueError(f"feature {index} has a null ID property {id_column!r}")
        region_id = str(raw_region_id).strip()
        if not region_id:
            raise ValueError(f"feature {index} has an empty ID property {id_column!r}")
        if region_id in seen:
            raise ValueError(f"duplicate region ID {region_id!r}")
        if not isinstance(geometry, Mapping) or not geometry.get("type"):
            raise ValueError(f"feature {index} has no geometry")
        seen.add(region_id)
        regions.append((region_id, dict(feature)))
    return dict(payload), regions


def bitwise_extract(ee: Any, image: Any, from_bit: int, to_bit: int) -> Any:
    mask_size = ee.Number(1).add(to_bit).subtract(from_bit)
    mask = ee.Number(1).leftShift(mask_size).subtract(1)
    return image.rightShift(from_bit).bitwiseAnd(mask)


def apply_modis_fire_masks(ee: Any, image: Any) -> Any:
    """Keep FireMask bits 0-3 >= 7 and QA bits 0-1 <= 2."""

    fire_condition = bitwise_extract(ee, image.select("FireMask"), 0, 3).gte(7)
    qa_condition = bitwise_extract(ee, image.select("QA"), 0, 1).lte(2)
    return image.updateMask(fire_condition.And(qa_condition))


def _modis_image(ee: Any, start: str, end: str, temporal_mode: str) -> Any:
    collection = (
        ee.ImageCollection(MODIS_COLLECTION)
        .filter(ee.Filter.date(start, end))
        .map(lambda image: apply_modis_fire_masks(ee, image))
        .select("MaxFRP")
    )
    mean_image = collection.mean().multiply(0.1).rename("MaxFRP_mean")
    max_image = collection.max().multiply(0.1).rename("MaxFRP_max")
    minimum = collection.max() if frp_min_reducer(temporal_mode) == "max" else collection.min()
    min_image = minimum.multiply(0.1).rename("MaxFRP_min")
    return mean_image.addBands(max_image).addBands(min_image)


def _modis_reducer(ee: Any) -> Any:
    return (
        ee.Reducer.mean()
        .combine(reducer2=ee.Reducer.max(), sharedInputs=True)
        .combine(reducer2=ee.Reducer.min(), sharedInputs=True)
    )


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    if not name:
        raise ValueError(f"cannot form a safe filename from {value!r}")
    return name


def _write_json(path: Path, payload: object, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"output exists; pass --overwrite to replace it: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _plan(args: argparse.Namespace, regions: Sequence[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    windows = month_windows(args.start_month, args.end_month, args.date_mode)
    return {
        "mode": "submit" if args.submit else "dry-run",
        "product": args.product,
        "collection": MODIS_COLLECTION if args.product == "mod14a1-frp" else FIRMS_COLLECTION,
        "country_label": args.country_label,
        "region_count": len(regions),
        "id_column": args.id_column,
        "date_mode": args.date_mode,
        "month_windows": [
            {"month": month, "start": start, "exclusive_end": end}
            for month, start, end in windows
        ],
        "output_count": len(windows) * (len(regions) if args.product == "mod14a1-frp" else 1),
        "output_directory": str(args.output_dir),
        "frp_temporal_mode": args.frp_temporal_mode if args.product == "mod14a1-frp" else None,
        "frp_min_definition": (
            "temporal maximum (historical notebook compatibility)"
            if args.product == "mod14a1-frp" and args.frp_temporal_mode == "historical"
            else "temporal minimum"
            if args.product == "mod14a1-frp"
            else None
        ),
        "scale": args.scale,
        "crs": args.crs,
        "tile_scale": 14 if args.product == "mod14a1-frp" else None,
        "best_effort": True if args.product == "mod14a1-frp" else None,
        "geometry_note": (
            "Historical FIRMS T21 used the dissolved FAO/GAUL/2015/level2 "
            "Indonesia geometry; caller GeoJSON must represent that same union "
            "for historical comparability. Feature IDs are ignored after validation."
            if args.product == "firms-t21"
            else "Caller GeoJSON features are reduced separately in EPSG:4326."
        ),
    }


def _submit_modis(
    ee: Any, args: argparse.Namespace, regions: Sequence[tuple[str, dict[str, Any]]]
) -> int:
    reducer = _modis_reducer(ee)
    written = 0
    for month, start, end in month_windows(args.start_month, args.end_month, args.date_mode):
        image = _modis_image(ee, start, end, args.frp_temporal_mode)
        for region_id, feature in regions:
            geometry = ee.Feature(feature).geometry()
            stats = image.reduceRegion(
                geometry=geometry,
                reducer=reducer,
                scale=args.scale,
                crs=args.crs,
                tileScale=14,
                bestEffort=True,
            ).getInfo()
            if not isinstance(stats, Mapping):
                raise RuntimeError(f"Earth Engine returned no mapping for {region_id} {month}")
            record = dict(stats)
            record.update({
                "GID": region_id,
                "GID_LEVEL": args.admin_level,
                "country": args.country_label,
                "date": start,
                "product": "MODIS/061/MOD14A1 MaxFRP (0.1 MW scale applied)",
                "date_mode": args.date_mode,
                "frp_temporal_mode": args.frp_temporal_mode,
            })
            path = args.output_dir / _safe_name(args.country_label) / f"{_safe_name(region_id)}_{month}.json"
            _write_json(path, record, args.overwrite)
            written += 1
    return written


def _submit_t21(
    ee: Any, args: argparse.Namespace, geojson: Mapping[str, Any]
) -> int:
    geometry = ee.FeatureCollection(geojson).geometry()
    written = 0
    for month, start, end in month_windows(args.start_month, args.end_month, args.date_mode):
        collection = (
            ee.ImageCollection(FIRMS_COLLECTION)
            .filter(ee.Filter.date(start, end))
            .select("T21")
        )
        mean_value = collection.mean().rename("Mean_T21").reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geometry, scale=args.scale, crs=args.crs
        ).get("Mean_T21").getInfo()
        max_value = collection.max().rename("Max_T21").reduceRegion(
            reducer=ee.Reducer.max(), geometry=geometry, scale=args.scale, crs=args.crs
        ).get("Max_T21").getInfo()
        record = {
            "Timestamp": start,
            "Mean_T21": mean_value,
            "Max_T21": max_value,
            "country": args.country_label,
            "product": "FIRMS T21 brightness temperature",
            "date_mode": args.date_mode,
        }
        path = args.output_dir / _safe_name(args.country_label) / f"FIRMS_T21_{month}.json"
        _write_json(path, record, args.overwrite)
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dry-run or submit MOD14A1 FRP and optional FIRMS T21 extraction."
    )
    parser.add_argument("--product", choices=("mod14a1-frp", "firms-t21"), default="mod14a1-frp")
    parser.add_argument("--geojson", required=True, type=Path, help="caller-supplied admin GeoJSON")
    parser.add_argument("--id-column", required=True, help="unique feature property used as region ID")
    parser.add_argument("--country-label", required=True, help="country label stored in every output")
    parser.add_argument("--admin-level", type=int, help="admin level stored in MODIS output")
    parser.add_argument("--start-month", required=True, metavar="YYYY-MM")
    parser.add_argument("--end-month", required=True, metavar="YYYY-MM")
    parser.add_argument("--date-mode", choices=("historical", "full-month"), default="historical",
                        help="historical excludes the last day; full-month includes it")
    parser.add_argument("--frp-temporal-mode", choices=("historical", "corrected"), default="historical",
                        help="historical reproduces MaxFRP_min via max(); corrected uses min()")
    parser.add_argument("--scale", type=int, default=1000)
    parser.add_argument("--crs", default="EPSG:4326")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--project", help="Google Cloud project, required with --submit")
    parser.add_argument("--overwrite", action="store_true")
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument("--submit", action="store_true",
                           help="initialize Earth Engine and write local JSON")
    execution.add_argument("--dry-run", action="store_true",
                           help="validate and print the offline plan (the default)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.scale <= 0:
            raise ValueError("--scale must be positive")
        if args.product == "mod14a1-frp" and args.admin_level is None:
            raise ValueError("--admin-level is required for mod14a1-frp")
        geojson, regions = _load_regions(args.geojson, args.id_column)
        plan = _plan(args, regions)
        if not args.submit:
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0
        ee = init_ee(args.project)
        written = (
            _submit_modis(ee, args, regions)
            if args.product == "mod14a1-frp"
            else _submit_t21(ee, args, geojson)
        )
        plan["written"] = written
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
