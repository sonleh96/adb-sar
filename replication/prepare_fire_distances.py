"""Add historical distances from admin centroids to the south-Vietnam centroid.

This ports ``docs/analysis/frp.ipynb`` cells 5-11 (one-based). The reference
geometry is the union of explicitly selected JAXA tile boxes. Both that union
and each admin geometry are projected to EPSG:3405 before centroid distance is
computed. Country and province filtering remain caller responsibilities.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise RuntimeError(f"{name} is required for fire-distance preparation") from exc


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"input does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON {path}: {exc}") from exc


def add_distances(
    admin_geojson: Path,
    tiles_json: Path,
    tile_ids: Sequence[str],
    id_column: str,
) -> dict[str, Any]:
    """Return a GeoJSON copy with historical centroid distances in kilometers."""

    shapely_geometry = _module("shapely.geometry")
    shapely_ops = _module("shapely.ops")
    pyproj = _module("pyproj")
    tiles = _read_json(tiles_json)
    if not isinstance(tiles, Mapping):
        raise ValueError("tile JSON must map tile IDs to [west, south, east, north]")
    requested = list(dict.fromkeys(tile_ids))
    if not requested:
        raise ValueError("at least one explicit --tile-id is required")
    missing = [tile_id for tile_id in requested if tile_id not in tiles]
    if missing:
        raise ValueError(f"tile IDs missing from {tiles_json}: {', '.join(missing)}")
    boxes = []
    for tile_id in requested:
        bounds = tiles[tile_id]
        if not isinstance(bounds, list) or len(bounds) != 4:
            raise ValueError(f"tile {tile_id!r} must have four bounds")
        west, south, east, north = map(float, bounds)
        if not all(math.isfinite(value) for value in (west, south, east, north)):
            raise ValueError(f"tile {tile_id!r} has non-finite bounds")
        if not (west < east and south < north):
            raise ValueError(f"tile {tile_id!r} has unordered bounds")
        boxes.append(shapely_geometry.box(west, south, east, north))

    payload = _read_json(admin_geojson)
    if not isinstance(payload, Mapping) or payload.get("type") != "FeatureCollection":
        raise ValueError("admin input must be a GeoJSON FeatureCollection")
    crs = payload.get("crs")
    if crs is not None:
        crs_name = str((crs.get("properties") or {}).get("name", "")).upper()
        if not (crs_name.endswith("EPSG::4326") or crs_name.endswith("EPSG:4326")
                or crs_name.endswith("CRS84")):
            raise ValueError("admin GeoJSON must use EPSG:4326 or RFC 7946 coordinates")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("admin GeoJSON must contain features")

    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3405", always_xy=True)
    reference = shapely_ops.transform(transformer.transform, shapely_ops.unary_union(boxes)).centroid
    output_features: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, feature in enumerate(features):
        properties = dict(feature.get("properties") or {})
        raw_id = properties.get(id_column)
        if raw_id is None or not str(raw_id).strip():
            raise ValueError(f"feature {index} has no non-null {id_column!r}")
        region_id = str(raw_id).strip()
        if region_id in seen:
            raise ValueError(f"duplicate admin ID {region_id!r}")
        geometry_data = feature.get("geometry")
        if not isinstance(geometry_data, Mapping):
            raise ValueError(f"feature {index} has no geometry")
        geometry = shapely_geometry.shape(geometry_data)
        if geometry.is_empty or not geometry.is_valid:
            raise ValueError(f"feature {region_id!r} has empty or invalid geometry")
        projected = shapely_ops.transform(transformer.transform, geometry)
        properties["distance_centroid_vn_south_km"] = projected.centroid.distance(reference) / 1000
        output_features.append({"type": "Feature", "properties": properties,
                                "geometry": geometry_data})
        seen.add(region_id)
    return {"type": "FeatureCollection", "features": output_features}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add EPSG:3405 centroid distances using explicit south-Vietnam JAXA tiles."
    )
    parser.add_argument("--admin-geojson", required=True, type=Path)
    parser.add_argument("--id-column", required=True)
    parser.add_argument("--tiles-json", required=True, type=Path)
    parser.add_argument("--tile-id", required=True, action="append",
                        help="reference tile ID; repeat in the historical order/selection")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.output.exists() and not args.overwrite:
            raise ValueError(f"output exists; pass --overwrite to replace it: {args.output}")
        payload = add_distances(args.admin_geojson, args.tiles_json, args.tile_id, args.id_column)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(f".{args.output.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, args.output)
        print(json.dumps({"output": str(args.output), "features": len(payload["features"]),
                          "reference_tile_ids": args.tile_id,
                          "distance_crs": "EPSG:3405"}, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
