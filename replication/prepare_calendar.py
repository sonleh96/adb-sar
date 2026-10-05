"""Convert and sample the historical rice harvest calendar.

This ports ``extract_channels.ipynb`` cells 30-31 and 42-48 (one-based).
The source files have ascending longitude and descending latitude. Therefore
the historical GeoTIFFs are not latitude-flipped, but their transform treats
coordinate centers as outer bounds. ``historical`` reproduces that transform;
``corrected`` uses inferred cell edges and enforces north-up row order.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import itertools
import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence


NODATA = -9999.0
CALENDAR_YEAR = 2019
GROUP_VARIABLES = tuple(f"Harvest_{index}_Group" for index in range(1, 4))
CROPPING_VARIABLES = tuple(f"Harvest_{index}_Cropping" for index in range(1, 4))
VARIABLES = GROUP_VARIABLES + CROPPING_VARIABLES


def _optional_module(name: str, purpose: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise RuntimeError(f"{name} is required to {purpose}") from exc


def _direction(values: Any, name: str) -> str:
    numpy = _optional_module("numpy", "inspect calendar coordinates")
    array = numpy.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2 or not numpy.isfinite(array).all():
        raise ValueError(f"{name} must be a finite one-dimensional coordinate")
    differences = numpy.diff(array)
    if numpy.all(differences > 0):
        return "ascending"
    if numpy.all(differences < 0):
        return "descending"
    raise ValueError(f"{name} must be strictly monotonic")


def _regular_step(values: Any, name: str) -> float:
    numpy = _optional_module("numpy", "validate calendar coordinates")
    differences = numpy.abs(numpy.diff(numpy.asarray(values, dtype=float)))
    step = float(differences[0])
    if not numpy.allclose(differences, step, rtol=1e-7, atol=1e-10):
        raise ValueError(f"{name} coordinate spacing is irregular")
    return step


def inspect_netcdf(path: Path, variables: Sequence[str]) -> dict[str, Any]:
    xarray = _optional_module("xarray", "read the calendar NetCDF")
    try:
        dataset = xarray.open_dataset(path)
    except Exception as exc:
        raise ValueError(f"cannot open NetCDF {path}: {exc}") from exc
    try:
        missing = [name for name in variables if name not in dataset]
        if missing:
            raise ValueError(f"{path} is missing variables: {', '.join(missing)}")
        lon_direction = _direction(dataset["lon"].values, "lon")
        lat_direction = _direction(dataset["lat"].values, "lat")
        return {
            "path": str(path),
            "longitude_orientation": lon_direction,
            "latitude_orientation": lat_direction,
            "historical_latitude_flip_present": lat_direction == "ascending",
            "shape": [int(dataset.sizes["lat"]), int(dataset.sizes["lon"])],
            "longitude_centers": [float(dataset.lon.values[0]), float(dataset.lon.values[-1])],
            "latitude_centers": [float(dataset.lat.values[0]), float(dataset.lat.values[-1])],
            "variables": list(variables),
        }
    finally:
        dataset.close()


def _transform(rasterio: Any, lon: Any, lat: Any, mode: str) -> Any:
    if mode == "historical":
        return rasterio.transform.from_bounds(
            float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max()),
            int(lon.size), int(lat.size),
        )
    lon_step = _regular_step(lon, "lon")
    lat_step = _regular_step(lat, "lat")
    west = float(lon.min()) - lon_step / 2
    north = float(lat.max()) + lat_step / 2
    return rasterio.transform.from_origin(west, north, lon_step, lat_step)


def convert_netcdf(
    source: Path,
    variables: Sequence[str],
    output_dir: Path,
    mode: str,
    overwrite: bool,
) -> list[Path]:
    xarray = _optional_module("xarray", "read the calendar NetCDF")
    numpy = _optional_module("numpy", "convert calendar arrays")
    rasterio = _optional_module("rasterio", "write calendar GeoTIFFs")
    dataset = xarray.open_dataset(source)
    outputs: list[Path] = []
    try:
        lon_direction = _direction(dataset.lon.values, "lon")
        lat_direction = _direction(dataset.lat.values, "lat")
        if lon_direction != "ascending":
            raise ValueError("historical calendar conversion expects ascending longitude")
        transform = _transform(rasterio, dataset.lon.values, dataset.lat.values, mode)
        output_dir.mkdir(parents=True, exist_ok=True)
        for variable in variables:
            if variable not in dataset:
                raise ValueError(f"{source} is missing variable {variable}")
            data = dataset[variable].transpose("lat", "lon").values
            if mode == "corrected" and lat_direction == "ascending":
                data = numpy.flipud(data)
            data = numpy.where(numpy.isfinite(data), data, NODATA).astype("float32")
            output = output_dir / f"marc_{variable.lower()}.tiff"
            if output.exists() and not overwrite:
                raise ValueError(f"output exists; pass --overwrite to replace it: {output}")
            temporary = output.with_name(f".{output.name}.tmp.tiff")
            try:
                with rasterio.open(
                    temporary,
                    "w",
                    driver="GTiff",
                    height=data.shape[0],
                    width=data.shape[1],
                    count=1,
                    dtype="float32",
                    crs="EPSG:4326",
                    transform=transform,
                    nodata=NODATA,
                ) as destination:
                    destination.write(data, 1)
                    destination.update_tags(
                        source_variable=variable,
                        replication_mode=mode,
                        source_latitude_orientation=lat_direction,
                    )
                os.replace(temporary, output)
            finally:
                if temporary.exists():
                    temporary.unlink()
            outputs.append(output)
    finally:
        dataset.close()
    return outputs


def _read_points(
    path: Path, lon_column: str, lat_column: str, limit: int | None
) -> tuple[list[dict[str, Any]], list[tuple[float, float]]]:
    if path.suffix.lower() in {".json", ".geojson"}:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(payload, dict) or payload.get("type") != "FeatureCollection"
                or not isinstance(payload.get("features"), list)):
            raise ValueError("point GeoJSON must be a FeatureCollection")
        rows: list[dict[str, Any]] = []
        coordinates: list[tuple[float, float]] = []
        features = payload["features"] if limit is None else payload["features"][:limit]
        for index, feature in enumerate(features):
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point" or len(geometry.get("coordinates", [])) < 2:
                raise ValueError(f"GeoJSON feature {index} is not a Point")
            lon, lat = map(float, geometry["coordinates"][:2])
            if not (math.isfinite(lon) and math.isfinite(lat)):
                raise ValueError(f"GeoJSON feature {index} has non-finite coordinates")
            row = dict(feature.get("properties") or {})
            row[lon_column], row[lat_column] = lon, lat
            rows.append(row)
            coordinates.append((lon, lat))
        return rows, coordinates

    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader if limit is None else itertools.islice(reader, limit))
    if not rows:
        raise ValueError("point CSV has no data rows")
    if lon_column not in rows[0] or lat_column not in rows[0]:
        raise ValueError(f"point CSV must contain {lon_column!r} and {lat_column!r}")
    try:
        coordinates = [(float(row[lon_column]), float(row[lat_column])) for row in rows]
    except (TypeError, ValueError) as exc:
        raise ValueError("point CSV contains non-numeric coordinates") from exc
    if not all(math.isfinite(lon) and math.isfinite(lat) for lon, lat in coordinates):
        raise ValueError("point CSV contains non-finite coordinates")
    return rows, coordinates


def _doy_to_month(value: float) -> int | None:
    if not math.isfinite(value) or value == NODATA:
        return None
    return (datetime(CALENDAR_YEAR, 1, 1) + timedelta(days=value - 1)).month


def _write_csv(path: Path, rows: Sequence[dict[str, Any]], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ValueError(f"output exists; pass --overwrite to replace it: {path}")
    if not rows:
        raise ValueError("cannot write an empty CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def sample_calendars(
    raster_dir: Path,
    point_path: Path,
    doy_output: Path,
    month_output: Path,
    lon_column: str,
    lat_column: str,
    month_columns: str,
    sampling_mode: str,
    limit: int | None,
    overwrite: bool,
) -> int:
    rasterio = _optional_module("rasterio", "sample calendar GeoTIFFs")
    rows, coordinates = _read_points(point_path, lon_column, lat_column, limit)
    doy_rows = [dict(row) for row in rows]
    for variable in VARIABLES:
        raster_path = raster_dir / f"marc_{variable.lower()}.tiff"
        if not raster_path.is_file():
            raise ValueError(f"calendar raster does not exist: {raster_path}")
        with rasterio.open(raster_path) as raster:
            values = [float(sample[0]) for sample in raster.sample(coordinates, masked=False)]
        column = f"{variable.lower()}_doy"
        for row, value in zip(doy_rows, values, strict=True):
            row[column] = None if not math.isfinite(value) or value == NODATA else value

    if sampling_mode == "historical":
        # Cell 45 replaced values in-place, so cell 46's file named "dates"
        # actually stored month values while retaining the *_doy headers.
        dates_rows = []
        for row in doy_rows:
            dates_row = dict(row)
            for variable in VARIABLES:
                name = f"{variable.lower()}_doy"
                value = dates_row[name]
                dates_row[name] = None if value is None else _doy_to_month(float(value))
            dates_rows.append(dates_row)
    else:
        dates_rows = doy_rows
    _write_csv(doy_output, dates_rows, overwrite)

    month_rows: list[dict[str, Any]] = []
    keep_variables = VARIABLES if month_columns == "all" else CROPPING_VARIABLES
    for row in dates_rows:
        month_row = {key: value for key, value in row.items() if not key.endswith("_doy")}
        for variable in keep_variables:
            doy_name = f"{variable.lower()}_doy"
            value = row[doy_name]
            month_row[doy_name.replace("_doy", "_moy")] = (
                value
                if sampling_mode == "historical" or value is None
                else _doy_to_month(float(value))
            )
        month_rows.append(month_row)
    _write_csv(month_output, month_rows, overwrite)
    return len(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert, inspect, and sample rice calendar inputs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="report NetCDF coordinate orientation")
    inspect_parser.add_argument("--group-netcdf", required=True, type=Path)
    inspect_parser.add_argument("--cropping-netcdf", required=True, type=Path)

    convert_parser = subparsers.add_parser("convert", help="convert six harvest variables to GeoTIFF")
    convert_parser.add_argument("--group-netcdf", required=True, type=Path)
    convert_parser.add_argument("--cropping-netcdf", required=True, type=Path)
    convert_parser.add_argument("--output-dir", required=True, type=Path)
    convert_parser.add_argument("--mode", choices=("historical", "corrected"), default="historical")
    convert_parser.add_argument("--overwrite", action="store_true")

    sample_parser = subparsers.add_parser("sample", help="sample GeoTIFFs to DOY and 2019 month CSVs")
    sample_parser.add_argument("--raster-dir", required=True, type=Path)
    sample_parser.add_argument("--points", required=True, type=Path, help="CSV or Point GeoJSON")
    sample_parser.add_argument("--dates-output", "--doy-output", dest="doy_output",
                               required=True, type=Path,
                               help="historical dates CSV path; --doy-output is a compatibility alias")
    sample_parser.add_argument("--month-output", required=True, type=Path)
    sample_parser.add_argument("--lon-column", default="lon")
    sample_parser.add_argument("--lat-column", default="lat")
    sample_parser.add_argument("--month-columns", choices=("cropping", "all"), default="cropping",
                               help="historical output keeps cropping month columns only")
    sample_parser.add_argument("--sampling-mode", choices=("historical", "corrected"),
                               default="historical",
                               help="historical writes months under *_doy in the dates CSV; corrected writes DOY")
    sample_parser.add_argument("--limit", type=int,
                               help="sample only the first N input points, useful for validation")
    sample_parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            report = {
                "group": inspect_netcdf(args.group_netcdf, GROUP_VARIABLES),
                "cropping": inspect_netcdf(args.cropping_netcdf, CROPPING_VARIABLES),
                "historical_transform_note": (
                    "source coordinate centers were passed to from_bounds as outer edges"
                ),
            }
            print(json.dumps(report, indent=2, sort_keys=True))
        elif args.command == "convert":
            outputs = convert_netcdf(args.group_netcdf, GROUP_VARIABLES, args.output_dir,
                                     args.mode, args.overwrite)
            outputs += convert_netcdf(args.cropping_netcdf, CROPPING_VARIABLES, args.output_dir,
                                      args.mode, args.overwrite)
            print(json.dumps({"mode": args.mode, "outputs": [str(path) for path in outputs],
                              "nodata": NODATA}, indent=2))
        else:
            if args.limit is not None and args.limit <= 0:
                raise ValueError("--limit must be positive")
            count = sample_calendars(args.raster_dir, args.points, args.doy_output,
                                     args.month_output, args.lon_column, args.lat_column,
                                     args.month_columns, args.sampling_mode, args.limit,
                                     args.overwrite)
            print(json.dumps({"points": count, "doy_output": str(args.doy_output),
                              "month_output": str(args.month_output),
                              "calendar_year": CALENDAR_YEAR, "sampling_mode": args.sampling_mode,
                              "raster_nodata": NODATA, "csv_missing": "blank"}, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
