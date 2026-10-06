"""Prepare monthly Black Marble rasters from local VNP46A3 HDF5 granules.

Ports the Python cleaning and full-year imputation in sonleh96/
wb_nightlights_production at 44f0c80ce8ecd89a4cea33f85efe7886c55faae1.
Uses equal month spacing and the previous cleaned December. Corrects the
upstream export index that otherwise labels that December as January.
Outputs un-clipped mosaics of the supplied tiles as VNM_bm_YYYY_MM.tif.

MIT License
Copyright (c) 2022 sonleh96

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack, contextmanager
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid


SOURCE = "https://github.com/sonleh96/wb_nightlights_production"
REVISION = "44f0c80ce8ecd89a4cea33f85efe7886c55faae1"
FIELDS = "HDFEOS/GRIDS/VIIRS_Grid_DNB_2d/Data Fields"
SCIENCE = "AllAngle_Composite_Snow_Free"
QUALITY = "AllAngle_Composite_Snow_Free_Quality"
LAND = "Land_Water_Mask"
GRANULE = re.compile(r"VNP46A3\.A(\d{4})(\d{3})\.(h\d{2}v\d{2})\.(\d{3})\.[^.]+\.h5$", re.I)


@contextmanager
def staging_directory(parent: Path):
    stage = parent / f".nightlights-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        yield stage
    finally:
        if stage.exists():
            stage.resolve().relative_to(parent.resolve())
            shutil.rmtree(stage)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_values(raw, quality, land, lit_mask):
    import numpy as np

    values = np.where(raw >= 0, raw, 0).astype("float64")
    values[(values >= 65535) | (quality == 1) | ~(land <= 150)] = np.nan
    values *= 0.1
    values[lit_mask == 0] = 0
    return values


def interpolate_months(values):
    """Match xarray linear/extrapolate on an implicit monthly index, then export."""
    import numpy as np

    result = values.copy()
    count = len(values)
    index = np.arange(count, dtype="int16")[:, None, None]
    valid = np.isfinite(values)
    previous = np.maximum.accumulate(np.where(valid, index, -1), axis=0)
    following = np.minimum.accumulate(np.where(valid, index, count)[::-1], axis=0)[::-1]
    first, last = following[0], previous[-1]
    second = np.min(np.where(valid & (index > first), index, count), axis=0)
    penultimate = np.max(np.where(valid & (index < last), index, -1), axis=0)
    enough = valid.sum(axis=0) >= 2
    for month in range(count):
        left = np.where(previous[month] < 0, first, previous[month])
        right = np.where(following[month] == count, last, following[month])
        right = np.where(previous[month] < 0, second, right)
        left = np.where(following[month] == count, penultimate, left)
        left = np.clip(left, 0, count - 1)
        right = np.clip(right, 0, count - 1)
        a = np.take_along_axis(values, left[None], axis=0)[0]
        b = np.take_along_axis(values, right[None], axis=0)[0]
        fraction = (month - left) / np.maximum(right - left, 1)
        result[month] = np.where(~valid[month] & enough, a + fraction * (b - a), values[month])
    # This also maps unresolved NaNs to zero, as the upstream xarray.where does.
    return np.where(result >= 0, result, 0).astype("float32")


def grid_from_h5(path: Path):
    import h5py
    import numpy as np
    from rasterio.transform import from_origin

    with h5py.File(path, "r") as h5:
        fields = h5[FIELDS]
        x, y = fields["lon"][:], fields["lat"][:]
        if x.ndim != 1 or y.ndim != 1 or min(len(x), len(y)) < 2:
            raise ValueError(f"Expected one-dimensional lon/lat pixel centres: {path}")
        dx, dy = float(x[-1] - x[0]) / (len(x) - 1), float(y[-1] - y[0]) / (len(y) - 1)
        tolerance = max([1e-8] + [float(np.finfo(a.dtype).eps * max(1, np.max(np.abs(a))) * 2)
                                 for a in (x, y) if np.issubdtype(a.dtype, np.floating)])
        if dx <= 0 or dy >= 0 or not np.allclose(x, x[0] + np.arange(len(x)) * dx, rtol=0, atol=tolerance) or not np.allclose(y, y[0] + np.arange(len(y)) * dy, rtol=0, atol=tolerance):
            raise ValueError(f"Expected regular eastward longitude and southward latitude: {path}")
        for band in (SCIENCE, QUALITY, LAND):
            if fields[band].shape != (len(y), len(x)):
                raise ValueError(f"Band shape does not match lon/lat: {path}: {band}")
        if x[0] < -180 or x[-1] > 180 or y[-1] < -90 or y[0] > 90:
            raise ValueError(f"Invalid longitude/latitude extent: {path}")
    return len(x), len(y), from_origin(float(x[0] - dx / 2), float(y[0] - dy / 2), dx, -dy)


def discover(input_dir: Path, years: list[int], collection: str, tiles: list[str]):
    records = {}
    required_dates = {(year, month) for year in years for month in range(1, 13)}
    required_dates.update((year - 1, 12) for year in years)
    versions = set()
    for path in sorted(input_dir.rglob("*.h5")):
        match = GRANULE.fullmatch(path.name)
        if not match:
            if path.name.upper().startswith("VNP46A3"):
                raise ValueError(f"Unrecognised VNP46A3 filename: {path}")
            continue
        year, doy, tile, version = match.groups()
        observed = date(int(year), 1, 1) + timedelta(days=int(doy) - 1)
        if observed.year != int(year) or observed.day != 1:
            raise ValueError(f"Monthly granule must be dated the first day of its month: {path}")
        tile = tile.lower()
        if (observed.year, observed.month) not in required_dates or (tiles and tile not in tiles):
            continue
        versions.add(version)
        key = (observed.year, observed.month, tile)
        if key in records:
            raise ValueError(f"Duplicate monthly tile {key}: {records[key]} and {path}")
        records[key] = path.resolve()
    if not records:
        raise ValueError("No requested VNP46A3 granules found")
    if versions != {collection}:
        raise ValueError(f"Expected only NASA collection {collection}; found {sorted(versions)}")
    selected_tiles = sorted(set(tiles) or {key[2] for key in records if key[0] in years})
    if not selected_tiles:
        raise ValueError("No tiles found for the requested years")
    missing = [(year, month, tile) for year, month in sorted(required_dates)
               for tile in selected_tiles if (year, month, tile) not in records]
    if missing:
        raise ValueError(f"Missing {len(missing)} monthly granules, including preceding clean December: {missing[:8]}")
    return {key: records[key] for key in sorted(records) if key[2] in selected_tiles}, selected_tiles


def parse_masks(assignments, reuse, required_years):
    masks = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if not separator or not value:
            raise ValueError("--mask must be YEAR=PATH")
        year = int(key)
        if year in masks:
            raise ValueError(f"Duplicate mask for {year}")
        path = Path(value).resolve()
        if not path.is_file():
            raise ValueError(f"Mask does not exist: {path}")
        masks[year] = (year, path)
    for assignment in reuse:
        key, separator, value = assignment.partition("=")
        if not separator:
            raise ValueError("--reuse-mask must be TARGET_YEAR=SOURCE_YEAR")
        target, source = int(key), int(value)
        if target in masks or source not in masks:
            raise ValueError(f"Mask reuse needs an unused target and an explicit existing source: {assignment}")
        masks[target] = masks[source]
    missing = sorted(required_years - masks.keys())
    if missing:
        raise ValueError(f"Explicit EOG mask or --reuse-mask required for years {missing}")
    return {year: masks[year] for year in sorted(required_years)}


def prepare(args) -> dict:
    import h5py
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.vrt import WarpedVRT
    from rasterio.windows import Window

    output = args.output_dir.resolve()
    if output.exists():
        raise ValueError(f"Output directory already exists; choose a new directory: {output}")
    years = sorted(set(args.year))
    records, tiles = discover(args.input_dir, years, args.collection, args.tile)
    required_years = {key[0] for key in records}
    masks = parse_masks(args.mask, args.reuse_mask, required_years)
    grids = {}
    for key, path in records.items():
        grid = grid_from_h5(path)
        if key[2] in grids:
            width, height, transform = grids[key[2]]
            if grid[:2] != (width, height) or not grid[2].almost_equals(transform, precision=1e-8):
                raise ValueError(f"Grid changed across months for {key[2]}: {path}")
        grids[key[2]] = grid
    dx, dy = grids[tiles[0]][2].a, -grids[tiles[0]][2].e
    west = min(grid[2].c for grid in grids.values())
    north = max(grid[2].f for grid in grids.values())
    offsets = {}
    for tile, (width, height, transform) in grids.items():
        if not np.isclose(transform.a, dx, rtol=0, atol=1e-8) or not np.isclose(-transform.e, dy, rtol=0, atol=1e-8):
            raise ValueError("Input tiles must have the same pixel size")
        col, row = (transform.c - west) / dx, (north - transform.f) / dy
        if abs(col - round(col)) > 0.01 or abs(row - round(row)) > 0.01:
            raise ValueError(f"Tile {tile} is not aligned with the mosaic grid")
        offsets[tile] = (round(col), round(row), width, height)
    rectangles = list(offsets.items())
    for i, (tile, (x, y, w, h)) in enumerate(rectangles):
        for other, (ox, oy, ow, oh) in rectangles[:i]:
            if x < ox + ow and x + w > ox and y < oy + oh and y + h > oy:
                raise ValueError(f"Overlapping input tiles: {tile}, {other}")
    width = max(x + w for x, y, w, h in offsets.values())
    height = max(y + h for x, y, w, h in offsets.values())
    profile = dict(driver="GTiff", width=width, height=height, count=1,
                   dtype="float32", crs="EPSG:4326", transform=from_origin(west, north, dx, dy),
                   nodata=np.nan, compress="deflate", tiled=True, blockxsize=256,
                   blockysize=256, BIGTIFF="IF_SAFER")
    manifest = {
        "upstream": {"url": SOURCE, "revision": REVISION, "language": "Python"},
        "collection": args.collection, "years": years, "tiles": tiles,
        "block_size": args.block_size,
        "cleaning": "negative raw -> 0; raw >=65535, quality==1 or land>150 -> NaN; scale 0.1; EOG mask==0 -> 0",
        "interpolation": "linear with endpoint extrapolation on equal month indices, each year plus previous cleaned December",
        "final_missing": "negative and unresolved NaN -> 0, matching upstream xarray.where(value >= 0, 0)",
        "source_bugfix": "Drop preceding December from the output data and filenames together; upstream impute_bm.py dropped it only from filenames",
        "spatial": "native lon/lat pixel-centre grid; nearest-neighbour EOG mask; mosaic supplied tiles without country polygon clipping",
        "mask_coverage": "Every selected HDF5 tile must be covered by a finite mask value; zero means unlit even when labelled nodata in mask metadata",
        "inputs": [{"path": str(path), "month": f"{key[0]:04d}-{key[1]:02d}", "tile": key[2], "sha256": sha256(path)}
                   for key, path in records.items()],
        "masks": [{"year": year, "source_year": source, "path": str(path), "sha256": sha256(path)}
                  for year, (source, path) in masks.items()],
        "outputs": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with staging_directory(output.parent) as stage:
        for year in years:
            months = [(year - 1, 12)] + [(year, month) for month in range(1, 13)]
            with ExitStack() as stack:
                writers = [stack.enter_context(rasterio.open(stage / f"VNM_bm_{year}_{month:02d}.tif", "w", **profile))
                           for month in range(1, 13)]
                for writer in writers:
                    writer.set_band_description(1, "b1")
                    writer.update_tags(units="nW cm-2 sr-1", upstream_revision=REVISION)
                    for row in range(0, height, args.block_size):
                        for col in range(0, width, args.block_size):
                            window = Window(col, row, min(args.block_size, width-col), min(args.block_size, height-row))
                            writer.write(np.full((int(window.height), int(window.width)), np.nan, dtype="float32"), 1, window=window)
                for tile in tiles:
                    tile_width, tile_height, transform = grids[tile]
                    with ExitStack() as inputs:
                        granules = [inputs.enter_context(h5py.File(records[(y, m, tile)], "r"))[FIELDS] for y, m in months]
                        warped_masks = {}
                        for mask_year in {year - 1, year}:
                            source_mask = inputs.enter_context(rasterio.open(masks[mask_year][1]))
                            if source_mask.crs is None or source_mask.count != 1:
                                raise ValueError(f"Mask must have a CRS and one band: {source_mask.name}")
                            warped_masks[mask_year] = inputs.enter_context(WarpedVRT(
                                source_mask, crs="EPSG:4326", transform=transform, width=tile_width,
                                height=tile_height, resampling=Resampling.nearest,
                                src_nodata=np.nan if source_mask.nodata == 0 else source_mask.nodata,
                                nodata=np.nan, dtype="float32"))
                        for row in range(0, tile_height, args.block_size):
                            for col in range(0, tile_width, args.block_size):
                                h, w = min(args.block_size, tile_height-row), min(args.block_size, tile_width-col)
                                window = Window(col, row, w, h)
                                mask_blocks = {y: vrt.read(1, window=window) for y, vrt in warped_masks.items()}
                                if any(np.any(~np.isfinite(block)) for block in mask_blocks.values()):
                                    raise ValueError(f"EOG mask does not cover all pixels of tile {tile}")
                                values = np.stack([clean_values(fields[SCIENCE][row:row+h, col:col+w],
                                                               fields[QUALITY][row:row+h, col:col+w],
                                                               fields[LAND][row:row+h, col:col+w], mask_blocks[y])
                                                   for fields, (y, m) in zip(granules, months)])
                                interpolated = interpolate_months(values)[1:]
                                x, y, _, _ = offsets[tile]
                                target_window = Window(x + col, y + row, w, h)
                                for month, writer in enumerate(writers):
                                    writer.write(interpolated[month], 1, window=target_window)
            for month in range(1, 13):
                path = stage / f"VNM_bm_{year}_{month:02d}.tif"
                manifest["outputs"].append({"file": path.name, "sha256": sha256(path)})
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("MIT License")[0])
    parser.add_argument("--input-dir", type=Path, required=True, help="local granules, searched recursively")
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for rasters and manifest")
    parser.add_argument("--year", type=int, action="append", required=True, help="complete calendar year to output; repeatable")
    parser.add_argument("--tile", action="append", default=[], help="select a tile such as h28v08; repeatable")
    parser.add_argument("--collection", default="001", help="required NASA collection number; mixed collections rejected")
    parser.add_argument("--mask", action="append", default=[], metavar="YEAR=PATH", help="annual EOG lit-area raster covering complete selected tiles; include previous December's year")
    parser.add_argument("--reuse-mask", action="append", default=[], metavar="TARGET=SOURCE", help="explicitly reuse another year's supplied mask")
    parser.add_argument("--block-size", type=int, default=256, help="window side in pixels")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.block_size < 1:
        parser.error("--block-size must be positive")
    if not args.input_dir.is_dir():
        parser.error("--input-dir must be an existing directory")
    if not re.fullmatch(r"\d{3}", args.collection):
        parser.error("--collection must be three digits, such as 001")
    if any(year < 2 or year > 9998 for year in args.year):
        parser.error("--year must be between 2 and 9998")
    try:
        manifest = prepare(args)
    except (ValueError, KeyError, OSError, ImportError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output_dir": str(args.output_dir.resolve()), "rasters": len(manifest["outputs"]),
                      "collection": manifest["collection"], "years": manifest["years"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
