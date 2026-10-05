"""Build portable JAXA 2-by-2 tile-bound JSON from raster metadata.

This ports ``split_jaxa_tiles.ipynb`` cells 4-6 (one-based). It only opens
raster metadata; pixel arrays are never read. The historical notebook did not
contain the upstream crop-mask production workflow, so this module does not
invent one.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Sequence


_JAXA_TILE = re.compile(r"^(?P<tile>[NS]\d{2}[EW]\d{3})")


def _rasterio() -> Any:
    try:
        return importlib.import_module("rasterio")
    except ImportError as exc:
        raise RuntimeError(
            "rasterio is required to inspect JAXA rasters; install the optional "
            "geospatial dependencies before running this command"
        ) from exc


def _find_rasters(inputs: Sequence[Path], pattern: str) -> list[Path]:
    found: list[Path] = []
    for value in inputs:
        if value.is_file():
            found.append(value)
        elif value.is_dir():
            found.extend(path for path in value.rglob(pattern) if path.is_file())
        else:
            raise ValueError(f"input path does not exist: {value}")
    unique = sorted({path.resolve() for path in found}, key=lambda path: str(path).lower())
    if not unique:
        raise ValueError(f"no rasters matched {pattern!r} in the supplied inputs")
    return unique


def _tile_name(path: Path) -> str:
    match = _JAXA_TILE.match(path.stem)
    if not match:
        raise ValueError(
            "filename must start with a JAXA tile ID such as N10E105: " f"{path.name}"
        )
    return match.group("tile")


def _bounds_for_raster(path: Path, rasterio: Any) -> dict[str, list[float]]:
    with rasterio.open(path) as dataset:
        if dataset.width <= 0 or dataset.height <= 0:
            raise ValueError("raster dimensions must be positive")
        transform = dataset.transform
        if not all(math.isfinite(float(value)) for value in tuple(transform)):
            raise ValueError("geotransform contains non-finite values")
        if abs(float(transform.b)) > 1e-12 or abs(float(transform.d)) > 1e-12:
            raise ValueError("rotated rasters are unsupported by the historical workflow")
        if float(transform.a) <= 0 or float(transform.e) >= 0:
            raise ValueError("expected a north-up geotransform with positive x and negative y scale")
        if dataset.crs is None or dataset.crs.to_epsg() != 4326:
            raise ValueError("expected an EPSG:4326 JAXA raster")
        west, south, east, north = map(float, dataset.bounds)

    if not all(math.isfinite(value) for value in (west, south, east, north)):
        raise ValueError("raster bounds contain non-finite values")
    if not (west < east and south < north):
        raise ValueError("raster bounds are unordered")

    tile = _tile_name(path)
    xmid = (west + east) / 2
    ymid = (south + north) / 2
    return {
        f"{tile}_0_0": [west, ymid, xmid, north],
        f"{tile}_0_1": [west, south, xmid, ymid],
        f"{tile}_1_0": [xmid, ymid, east, north],
        f"{tile}_1_1": [xmid, south, east, ymid],
    }


def build_tile_bounds(paths: Sequence[Path]) -> tuple[dict[str, list[float]], list[str]]:
    """Read metadata and return valid subtile bounds plus explicit errors."""

    rasterio = _rasterio()
    output: dict[str, list[float]] = {}
    errors: list[str] = []
    seen_tiles: dict[str, Path] = {}
    for path in paths:
        try:
            tile = _tile_name(path)
            if tile in seen_tiles:
                raise ValueError(f"duplicate tile ID also supplied by {seen_tiles[tile]}")
            additions = _bounds_for_raster(path, rasterio)
            overlap = set(output).intersection(additions)
            if overlap:
                raise ValueError(f"duplicate subtile IDs: {', '.join(sorted(overlap))}")
            output.update(additions)
            seen_tiles[tile] = path
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    return output, errors


def _write_json(path: Path, payload: object, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"output exists; pass --overwrite to replace it: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Split EPSG:4326 JAXA raster bounds into historical 2-by-2 subtiles."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="raster files or directories")
    parser.add_argument("--pattern", default="*.tif", help="recursive directory glob")
    parser.add_argument("--output", required=True, type=Path, help="output bounds JSON")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rasters = _find_rasters(args.inputs, args.pattern)
        bounds, errors = build_tile_bounds(rasters)
        if not bounds:
            detail = "; ".join(errors) if errors else "no diagnostic was returned"
            raise ValueError(f"all input rasters were invalid: {detail}")
        _write_json(args.output, bounds, args.overwrite)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({"output": str(args.output), "rasters": len(bounds) // 4,
                      "subtiles": len(bounds), "skipped": len(errors)}, indent=2))
    for error in errors:
        print(f"error: skipped invalid raster: {error}", file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
