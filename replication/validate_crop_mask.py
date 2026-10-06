"""Validate crop-mask mosaicking with real pixels and small GeoTIFF fixtures.

The validator invokes the public ``python -m replication.prepare_crop_mask``
CLI. It verifies an exact window copied from an original JAXA raster, a literal
two-tile categorical mosaic with nodata, safe refusal to overwrite, and
rejection of overlapping inputs. No Earth Engine access is used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Sequence


JAXA_RESOLUTION = 1 / 11133


def _module(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise RuntimeError(f"{name} is required for crop-mask validation") from exc


def _run_cli(arguments: Sequence[str]) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "replication.prepare_crop_mask", *arguments],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_fixture(
    rasterio: Any,
    path: Path,
    data: Any,
    *,
    west: float,
    north: float,
    nodata: int | None,
    colormap: dict[int, tuple[int, int, int, int]] | None = None,
) -> None:
    transform = rasterio.transform.from_origin(
        west, north, JAXA_RESOLUTION, JAXA_RESOLUTION
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=data.shape[1],
        height=data.shape[0],
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as destination:
        destination.write(data, 1)
        if colormap:
            destination.write_colormap(1, colormap)


def _validate_real_window(rasterio: Any, numpy: Any, source_path: Path, root: Path) -> dict[str, Any]:
    input_dir = root / "real-input"
    input_dir.mkdir()
    tile_path = input_dir / "real-window.tif"
    output = root / "real-mosaic.tif"
    with rasterio.open(source_path) as source:
        width = min(64, source.width)
        height = min(64, source.height)
        col_off = max(0, (source.width - width) // 2)
        row_off = max(0, (source.height - height) // 2)
        window = rasterio.windows.Window(col_off, row_off, width, height)
        expected = source.read(1, window=window)
        transform = source.window_transform(window)
        try:
            colormap = source.colormap(1)
        except ValueError:
            colormap = None
        with rasterio.open(
            tile_path,
            "w",
            driver="GTiff",
            width=width,
            height=height,
            count=1,
            dtype="uint8",
            crs=source.crs,
            transform=transform,
            nodata=source.nodata,
        ) as tile:
            tile.write(expected, 1)
            if colormap:
                tile.write_colormap(1, colormap)

    result = _run_cli(
        [
            "--input-dir",
            str(input_dir),
            "--output",
            str(output),
            "--chunk-rows",
            "17",
            "--write",
        ]
    )
    if result.returncode != 0:
        raise AssertionError(f"real-window CLI failed: {result.stderr or result.stdout}")
    with rasterio.open(output) as mosaic:
        actual = mosaic.read(1)
        if not numpy.array_equal(actual, expected):
            raise AssertionError("real JAXA window values changed during mosaic")
        if mosaic.transform != transform:
            raise AssertionError("real JAXA window transform changed during mosaic")
        if mosaic.descriptions != ("b1",):
            raise AssertionError(f"unexpected output band description: {mosaic.descriptions}")
    return {
        "source": str(source_path),
        "window": [col_off, row_off, width, height],
        "classes": sorted(int(value) for value in numpy.unique(expected)),
    }


def _validate_adjacent_and_overlap(rasterio: Any, numpy: Any, root: Path) -> dict[str, Any]:
    adjacent = root / "adjacent-input"
    adjacent.mkdir()
    left = numpy.array([[3, 3], [0, 4]], dtype="uint8")
    right = numpy.array([[4, 4], [3, 0]], dtype="uint8")
    palette = {0: (0, 0, 0, 0), 3: (255, 193, 191, 255), 4: (255, 255, 0, 255)}
    _write_fixture(
        rasterio,
        adjacent / "left.tif",
        left,
        west=0,
        north=2 * JAXA_RESOLUTION,
        nodata=0,
        colormap=palette,
    )
    _write_fixture(
        rasterio,
        adjacent / "right.tif",
        right,
        west=2 * JAXA_RESOLUTION,
        north=2 * JAXA_RESOLUTION,
        nodata=0,
        colormap=palette,
    )
    output = root / "adjacent-mosaic.tif"
    manifest = root / "adjacent-manifest.json"
    result = _run_cli(
        [
            "--input-dir",
            str(adjacent),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
            "--chunk-rows",
            "1",
            "--write",
        ]
    )
    if result.returncode != 0:
        raise AssertionError(f"adjacent-tile CLI failed: {result.stderr or result.stdout}")
    expected = numpy.array([[3, 3, 4, 4], [0, 4, 3, 0]], dtype="uint8")
    with rasterio.open(output) as mosaic:
        actual = mosaic.read(1)
        if not numpy.array_equal(actual, expected):
            raise AssertionError(f"adjacent mosaic differs: {actual.tolist()}")
        expected_bounds = rasterio.coords.BoundingBox(
            0, 0, 4 * JAXA_RESOLUTION, 2 * JAXA_RESOLUTION
        )
        if mosaic.nodata != 0 or mosaic.bounds != expected_bounds:
            raise AssertionError("adjacent mosaic nodata or bounds are wrong")
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    if manifest_payload["class_pixel_counts_in_sources"] != {"0": 2, "3": 3, "4": 3}:
        raise AssertionError("manifest class counts are wrong")

    original_hash = _sha256(output)
    refusal = _run_cli(
        ["--input-dir", str(adjacent), "--output", str(output), "--write"]
    )
    if refusal.returncode != 2 or "output exists" not in refusal.stderr:
        raise AssertionError("existing output was not safely refused")
    if _sha256(output) != original_hash:
        raise AssertionError("existing output changed after overwrite refusal")

    blocked_output = root / "blocked-by-manifest.tif"
    refusal = _run_cli(
        [
            "--input-dir",
            str(adjacent),
            "--output",
            str(blocked_output),
            "--manifest",
            str(manifest),
            "--write",
        ]
    )
    if refusal.returncode != 2 or "manifest exists" not in refusal.stderr:
        raise AssertionError("existing manifest was not refused during preflight")
    if blocked_output.exists():
        raise AssertionError("manifest preflight refusal left an output mosaic")

    source_hash = _sha256(adjacent / "left.tif")
    refusal = _run_cli(
        [
            "--input-dir",
            str(adjacent),
            "--output",
            str(root / "blocked-by-source-alias.tif"),
            "--manifest",
            str(adjacent / "left.tif"),
            "--overwrite",
            "--write",
        ]
    )
    if refusal.returncode != 2 or "must not overwrite an input tile" not in refusal.stderr:
        raise AssertionError("manifest aliasing an input tile was not refused")
    if _sha256(adjacent / "left.tif") != source_hash:
        raise AssertionError("input tile changed after manifest alias refusal")

    overlap = root / "overlap-input"
    overlap.mkdir()
    _write_fixture(
        rasterio,
        overlap / "first.tif",
        left,
        west=0,
        north=2 * JAXA_RESOLUTION,
        nodata=0,
        colormap=palette,
    )
    _write_fixture(
        rasterio,
        overlap / "second.tif",
        right,
        west=JAXA_RESOLUTION,
        north=2 * JAXA_RESOLUTION,
        nodata=0,
        colormap=palette,
    )
    overlap_output = root / "overlap-mosaic.tif"
    rejected = _run_cli(
        ["--input-dir", str(overlap), "--output", str(overlap_output), "--write"]
    )
    if rejected.returncode != 2 or "overlap" not in rejected.stderr:
        raise AssertionError("overlapping tiles were not rejected")
    if overlap_output.exists():
        raise AssertionError("overlap rejection left an output file")
    return {
        "adjacent_expected": expected.tolist(),
        "nodata": 0,
        "overwrite_refused": True,
        "manifest_preflight_refused": True,
        "manifest_source_alias_refused": True,
        "overlap_refused": True,
    }


def validate(real_raster: Path) -> dict[str, Any]:
    if not real_raster.is_file():
        raise ValueError(f"real JAXA raster does not exist: {real_raster}")
    rasterio = _module("rasterio")
    numpy = _module("numpy")
    root = Path(__file__).resolve().parents[1] / f"crop-mask-validation-{uuid.uuid4().hex}"
    root.mkdir()
    try:
        real = _validate_real_window(rasterio, numpy, real_raster.resolve(), root)
        fixtures = _validate_adjacent_and_overlap(rasterio, numpy, root)
    finally:
        shutil.rmtree(root, ignore_errors=False)
    return {
        "status": "pass",
        "real_window": real,
        "categorical_fixtures": fixtures,
        "limitation": "The full 60-tile mosaic was planned from metadata but not written by this validator.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-raster", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = validate(args.real_raster)
    except (AssertionError, OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"validation failed: {exc}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
