"""Build the historical JAXA Vietnam 2020 v23.09 class mosaic.

The visible extraction source in ``process_datasets.ipynb`` cells 13 and 15
(one-based) reads a private ``LULC_VN`` Earth Engine image, reprojects it to
EPSG:4326 at 10 m, and selects rice with ``b1 == 3``. The user confirmed that
the private image was made by simply mosaicking the 60 original JAXA tiles.
This command reproduces only that mosaic. It keeps all official class IDs and
does not create a binary rice raster or add an undocumented clip.

Official acquisition: register with JAXA at the product page, then download
all 60 GeoTIFF tiles for ``2020VNM_v23.09``. JAXA documents WGS84, 1-degree
tiles of 11,133 pixels, 1/11,133-degree cells, classes 1 through 12, and rice
as class 3. The command never downloads or uploads data.

https://www.eorc.jaxa.jp/ALOS/en/dataset/lulc/lulc_vnm_v2309_e.htm
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


PRODUCT = "JAXA HRLULC-Vietnam 2020VNM_v23.09"
PRODUCT_URL = "https://www.eorc.jaxa.jp/ALOS/en/dataset/lulc/lulc_vnm_v2309_e.htm"
VALID_CLASS_MIN = 1
VALID_CLASS_MAX = 12
RICE_CLASS = 3
OUTPUT_NODATA = 0
EXPECTED_EPSG = 4326
EXPECTED_RESOLUTION = 1 / 11133


@dataclass(frozen=True)
class Placement:
    path: Path
    col_off: int
    row_off: int
    width: int
    height: int
    source_nodata: int | None


@dataclass(frozen=True)
class MosaicPlan:
    crs: str
    dtype: str
    transform: Any
    width: int
    height: int
    resolution: tuple[float, float]
    bounds: tuple[float, float, float, float]
    placements: tuple[Placement, ...]
    colormap: dict[int, tuple[int, int, int, int]] | None


def _rasterio() -> Any:
    try:
        return importlib.import_module("rasterio")
    except ImportError as exc:
        raise RuntimeError(
            "rasterio is required to inspect or write the JAXA mosaic; "
            "install the documented geospatial dependencies"
        ) from exc


def discover_tiles(input_dir: Path, pattern: str) -> list[Path]:
    if not input_dir.is_dir():
        raise ValueError(f"input directory does not exist: {input_dir}")
    paths = sorted(path.resolve() for path in input_dir.glob(pattern) if path.is_file())
    if not paths:
        raise ValueError(f"no input tiles match {pattern!r} in {input_dir}")
    return paths


def _aligned_offset(delta: float, resolution: float, label: str, path: Path) -> int:
    pixels = delta / resolution
    rounded = round(pixels)
    if not math.isclose(pixels, rounded, rel_tol=0, abs_tol=1e-6):
        raise ValueError(f"{path.name} is not aligned to the common grid at {label}")
    return int(rounded)


def _overlap(first: Placement, second: Placement) -> bool:
    return (
        first.col_off < second.col_off + second.width
        and second.col_off < first.col_off + first.width
        and first.row_off < second.row_off + second.height
        and second.row_off < first.row_off + first.height
    )


def inspect_tiles(paths: Sequence[Path]) -> MosaicPlan:
    """Validate source metadata and return an exact, no-resampling layout."""

    if not paths:
        raise ValueError("at least one input tile is required")
    rasterio = _rasterio()
    metadata: list[dict[str, Any]] = []
    reference_colormap: dict[int, tuple[int, int, int, int]] | None = None
    colormap_initialized = False
    for path in paths:
        with rasterio.open(path) as source:
            if source.count != 1:
                raise ValueError(f"{path.name} must have exactly one band")
            if source.dtypes[0] != "uint8":
                raise ValueError(f"{path.name} must use uint8 class IDs")
            if source.crs is None:
                raise ValueError(f"{path.name} has no CRS")
            if source.crs.to_epsg() != EXPECTED_EPSG:
                raise ValueError(f"{path.name} must use the official EPSG:4326 grid")
            if source.transform.b != 0 or source.transform.d != 0:
                raise ValueError(f"{path.name} is rotated and cannot be copied without resampling")
            if source.transform.a <= 0 or source.transform.e >= 0:
                raise ValueError(f"{path.name} must be a north-up raster")
            if source.nodata not in (None, OUTPUT_NODATA):
                raise ValueError(
                    f"{path.name} uses nodata {source.nodata}; expected none or {OUTPUT_NODATA}"
                )
            try:
                colormap = source.colormap(1)
            except ValueError:
                colormap = None
            if not colormap_initialized:
                reference_colormap = colormap
                colormap_initialized = True
            elif colormap != reference_colormap:
                raise ValueError(f"{path.name} has a different class color table")
            metadata.append(
                {
                    "path": path,
                    "crs": source.crs,
                    "transform": source.transform,
                    "bounds": source.bounds,
                    "width": source.width,
                    "height": source.height,
                    "nodata": source.nodata,
                }
            )

    reference = metadata[0]
    xres = float(reference["transform"].a)
    yres = abs(float(reference["transform"].e))
    if not math.isclose(xres, EXPECTED_RESOLUTION, rel_tol=0, abs_tol=1e-12):
        raise ValueError("input tiles do not use the official 1/11133-degree x resolution")
    if not math.isclose(yres, EXPECTED_RESOLUTION, rel_tol=0, abs_tol=1e-12):
        raise ValueError("input tiles do not use the official 1/11133-degree y resolution")
    for item in metadata[1:]:
        if item["crs"] != reference["crs"]:
            raise ValueError(f"{item['path'].name} has a different CRS")
        if not math.isclose(float(item["transform"].a), xres, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"{item['path'].name} has a different x resolution")
        if not math.isclose(abs(float(item["transform"].e)), yres, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"{item['path'].name} has a different y resolution")

    west = min(float(item["bounds"].left) for item in metadata)
    south = min(float(item["bounds"].bottom) for item in metadata)
    east = max(float(item["bounds"].right) for item in metadata)
    north = max(float(item["bounds"].top) for item in metadata)
    width = _aligned_offset(east - west, xres, "mosaic width", paths[0])
    height = _aligned_offset(north - south, yres, "mosaic height", paths[0])
    transform = rasterio.transform.from_origin(west, north, xres, yres)

    placements: list[Placement] = []
    for item in metadata:
        placement = Placement(
            path=item["path"],
            col_off=_aligned_offset(float(item["bounds"].left) - west, xres, "x", item["path"]),
            row_off=_aligned_offset(north - float(item["bounds"].top), yres, "y", item["path"]),
            width=int(item["width"]),
            height=int(item["height"]),
            source_nodata=None if item["nodata"] is None else int(item["nodata"]),
        )
        if placement.col_off + placement.width > width or placement.row_off + placement.height > height:
            raise ValueError(f"{item['path'].name} falls outside the computed mosaic")
        for earlier in placements:
            if _overlap(earlier, placement):
                raise ValueError(
                    f"input tiles overlap: {earlier.path.name} and {placement.path.name}; "
                    "the confirmed historical operation was a simple non-overlapping mosaic"
                )
        placements.append(placement)

    return MosaicPlan(
        crs=str(reference["crs"]),
        dtype="uint8",
        transform=transform,
        width=width,
        height=height,
        resolution=(xres, yres),
        bounds=(west, south, east, north),
        placements=tuple(placements),
        colormap=reference_colormap,
    )


def plan_summary(plan: MosaicPlan, output: Path, chunk_rows: int) -> dict[str, Any]:
    return {
        "mode": "dry-run",
        "product": PRODUCT,
        "source_url": PRODUCT_URL,
        "source_count": len(plan.placements),
        "output": str(output),
        "crs": plan.crs,
        "dtype": plan.dtype,
        "band": "b1-compatible categorical classes",
        "valid_classes": [VALID_CLASS_MIN, VALID_CLASS_MAX],
        "rice_class": RICE_CLASS,
        "nodata": OUTPUT_NODATA,
        "width": plan.width,
        "height": plan.height,
        "bounds": list(plan.bounds),
        "resolution": list(plan.resolution),
        "uncompressed_bytes": plan.width * plan.height,
        "chunk_rows": chunk_rows,
        "maximum_source_buffer_bytes": max(item.width for item in plan.placements) * chunk_rows,
        "resampling": "none; exact aligned window copies",
        "overlap_policy": "reject",
    }


def _write_json(path: Path, payload: object, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"manifest exists; pass --overwrite to replace it: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    handle.close()
    try:
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if path.exists() and not overwrite:
            raise ValueError(f"manifest appeared during processing: {path}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_mosaic(
    plan: MosaicPlan,
    output: Path,
    *,
    chunk_rows: int,
    overwrite: bool,
) -> dict[str, Any]:
    """Write the mosaic with bounded source reads and no resampling."""

    if chunk_rows <= 0:
        raise ValueError("chunk_rows must be positive")
    output = output.resolve()
    if output in {placement.path.resolve() for placement in plan.placements}:
        raise ValueError("output must not overwrite an input tile")
    if output.exists() and not overwrite:
        raise ValueError(f"output exists; pass --overwrite to replace it: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    rasterio = _rasterio()
    numpy = importlib.import_module("numpy")
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{output.stem}.", suffix=".tmp.tif", dir=output.parent, delete=False
    )
    temporary = Path(handle.name)
    handle.close()
    temporary.unlink()
    counts = numpy.zeros(VALID_CLASS_MAX + 1, dtype="uint64")
    try:
        profile = {
            "driver": "GTiff",
            "width": plan.width,
            "height": plan.height,
            "count": 1,
            "dtype": plan.dtype,
            "crs": plan.crs,
            "transform": plan.transform,
            "nodata": OUTPUT_NODATA,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
            "compress": "deflate",
            "predictor": 1,
            "BIGTIFF": "YES",
            "SPARSE_OK": "TRUE",
        }
        with rasterio.open(temporary, "w", **profile) as destination:
            destination.set_band_description(1, "b1")
            destination.update_tags(
                product=PRODUCT,
                source_url=PRODUCT_URL,
                processing="aligned categorical mosaic only; no resampling or binary conversion",
                rice_class=str(RICE_CLASS),
            )
            if plan.colormap:
                destination.write_colormap(1, plan.colormap)
            for placement in plan.placements:
                with rasterio.open(placement.path) as source:
                    for source_row in range(0, placement.height, chunk_rows):
                        rows = min(chunk_rows, placement.height - source_row)
                        source_window = rasterio.windows.Window(0, source_row, placement.width, rows)
                        data = source.read(1, window=source_window)
                        invalid = data > VALID_CLASS_MAX
                        if invalid.any():
                            values = sorted(int(value) for value in numpy.unique(data[invalid]))
                            raise ValueError(
                                f"{placement.path.name} contains non-JAXA class IDs: {values}"
                            )
                        chunk_counts = numpy.bincount(
                            data.ravel(), minlength=len(counts)
                        )[: len(counts)].astype("uint64", copy=False)
                        counts += chunk_counts
                        target_window = rasterio.windows.Window(
                            placement.col_off,
                            placement.row_off + source_row,
                            placement.width,
                            rows,
                        )
                        destination.write(data, 1, window=target_window)
        if output.exists() and not overwrite:
            raise ValueError(f"output appeared during processing: {output}")
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        **plan_summary(plan, output, chunk_rows),
        "mode": "written",
        "class_pixel_counts_in_sources": {
            str(index): int(counts[index]) for index in range(len(counts)) if counts[index]
        },
        "source_files": [placement.path.name for placement in plan.placements],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mosaic JAXA Vietnam 2020 v23.09 class tiles without resampling.",
        epilog=(
            "Register and download all 60 original GeoTIFF tiles from the official JAXA product "
            f"page: {PRODUCT_URL}. Class 3 is rice. The output retains classes 1-12; upload the "
            "single band to Earth Engine as b1 for the existing extraction commands."
        ),
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--pattern", default="*.tif")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, help="optional JSON provenance and class-count manifest")
    parser.add_argument("--chunk-rows", type=int, default=512)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the mosaic; default is a metadata-only dry run",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.chunk_rows <= 0:
            raise ValueError("--chunk-rows must be positive")
        paths = discover_tiles(args.input_dir, args.pattern)
        plan = inspect_tiles(paths)
        if args.manifest:
            manifest = args.manifest.resolve()
            output = args.output.resolve()
            sources = {placement.path.resolve() for placement in plan.placements}
            if manifest == output:
                raise ValueError("--manifest and --output must be different paths")
            if manifest in sources:
                raise ValueError("--manifest must not overwrite an input tile")
            if args.write and manifest.exists() and not args.overwrite:
                raise ValueError(f"manifest exists; pass --overwrite to replace it: {manifest}")
        if not args.write:
            result = plan_summary(plan, args.output, args.chunk_rows)
        else:
            result = write_mosaic(
                plan,
                args.output,
                chunk_rows=args.chunk_rows,
                overwrite=args.overwrite,
            )
            if args.manifest:
                _write_json(args.manifest, result, args.overwrite)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
