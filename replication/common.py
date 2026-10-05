"""Offline-safe helpers shared by the extraction command-line programs.

Date behavior follows ``process_datasets.ipynb`` cells 13, 15, 29, 30, 34,
and 35 (one-based). The historical notebooks passed the last calendar day as
Earth Engine's exclusive ``filterDate`` end. ``date_mode='historical'`` keeps
that behavior; ``date_mode='full-month'`` uses the first day of the next month.
"""

from __future__ import annotations

import argparse
import calendar
import importlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from .config import DEFAULT_CROP_MASK_ASSET, DEFAULT_CRS, DEFAULT_SCALE, ExtractionConfig


_TILE_ID = re.compile(
    r"^(?P<lat_hemi>[NS])(?P<lat>\d{2})(?P<lon_hemi>[EW])"
    r"(?P<lon>\d{3})_(?P<x>[01])_(?P<y>[01])$"
)


def _parse_month(value: str) -> date:
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid month {value!r}; expected YYYY-MM") from exc
    if parsed.strftime("%Y-%m") != value:
        raise ValueError(f"invalid month {value!r}; expected zero-padded YYYY-MM")
    return parsed


def _next_month(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def month_windows(
    start_month: str,
    end_month: str,
    date_mode: str = "historical",
) -> tuple[tuple[str, str, str], ...]:
    """Return inclusive month labels with Earth Engine exclusive date bounds.

    Each item is ``(month, start_date, exclusive_end)``. In historical mode,
    the exclusive end is the month's last calendar day, reproducing the source
    notebooks' omission of observations on that day. Full-month mode uses the
    next month's first day and therefore includes the entire named month.
    """

    if date_mode not in {"historical", "full-month"}:
        raise ValueError("date_mode must be 'historical' or 'full-month'")
    current = _parse_month(start_month)
    final = _parse_month(end_month)
    if current > final:
        raise ValueError("start_month must not be after end_month")

    windows: list[tuple[str, str, str]] = []
    while current <= final:
        month = current.strftime("%Y-%m")
        if date_mode == "historical":
            last_day = calendar.monthrange(current.year, current.month)[1]
            exclusive_end = date(current.year, current.month, last_day)
        else:
            exclusive_end = _next_month(current)
        windows.append((month, current.isoformat(), exclusive_end.isoformat()))
        if current == final:
            break
        current = _next_month(current)
    return tuple(windows)


def init_ee(project: str) -> Any:
    """Import and initialize Earth Engine for explicit submission.

    Authentication is deliberately absent. Run ``earthengine authenticate``
    separately if the local credential store has not already been configured.
    """

    if not project or not project.strip():
        raise ValueError("--project is required with --submit")
    try:
        ee = importlib.import_module("ee")
    except ImportError as exc:
        raise RuntimeError(
            "earthengine-api is required for --submit; install it before submitting"
        ) from exc
    try:
        ee.Initialize(project=project.strip())
    except Exception as exc:
        raise RuntimeError(
            "Earth Engine initialization failed. Configure credentials separately "
            "and verify the --project value; this command does not authenticate."
        ) from exc
    return ee


def tile_bounds_from_id(tile_id: str) -> tuple[float, float, float, float]:
    """Derive the historical 0.5-degree JAXA subtile bounds from its ID."""

    match = _TILE_ID.fullmatch(tile_id)
    if not match:
        raise ValueError(
            f"invalid tile ID {tile_id!r}; expected a value such as N10E105_0_1"
        )
    groups = match.groupdict()
    latitude = int(groups["lat"]) * (1 if groups["lat_hemi"] == "N" else -1)
    longitude = int(groups["lon"]) * (1 if groups["lon_hemi"] == "E" else -1)
    west = longitude + int(groups["x"]) * 0.5
    south = latitude + (0.5 if groups["y"] == "0" else 0.0)
    return _validate_bbox(tile_id, (west, south, west + 0.5, south + 0.5))


def _validate_bbox(tile_id: str, value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        raise ValueError(f"tile {tile_id!r} must contain [west, south, east, north]")
    try:
        west, south, east, north = (float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"tile {tile_id!r} has non-numeric bounds") from exc
    if not all(math.isfinite(item) for item in (west, south, east, north)):
        raise ValueError(f"tile {tile_id!r} has non-finite bounds")
    if not (west < east and south < north):
        raise ValueError(f"tile {tile_id!r} has unordered bounds")
    if west < -180 or east > 180 or south < -90 or north > 90:
        raise ValueError(f"tile {tile_id!r} has bounds outside valid longitude/latitude limits")
    return west, south, east, north


def resolve_tiles(
    tiles_json: str | Path | None,
    tile_ids: Sequence[str] = (),
) -> dict[str, tuple[float, float, float, float]]:
    """Resolve tiles from a JSON mapping or directly from JAXA subtile IDs."""

    requested = tuple(dict.fromkeys(tile_ids))
    if tiles_json is None:
        if not requested:
            raise ValueError("provide --tiles-json or at least one --tile-id")
        return {tile_id: tile_bounds_from_id(tile_id) for tile_id in requested}

    path = Path(tiles_json)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"tile JSON does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"tile JSON is invalid: {path}: {exc}") from exc
    if not isinstance(payload, Mapping) or not payload:
        raise ValueError("tile JSON must be a non-empty object mapping IDs to bounds")

    available = {str(key): _validate_bbox(str(key), value) for key, value in payload.items()}
    if not requested:
        return available
    missing = [tile_id for tile_id in requested if tile_id not in available]
    if missing:
        raise ValueError(f"tile IDs missing from {path}: {', '.join(missing)}")
    return {tile_id: available[tile_id] for tile_id in requested}


def add_common_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_output_folder: str,
) -> None:
    """Add the shared portable, offline-safe CLI options to ``parser``."""

    parser.add_argument("--start-month", required=True, metavar="YYYY-MM")
    parser.add_argument("--end-month", required=True, metavar="YYYY-MM")
    parser.add_argument(
        "--date-mode",
        choices=("historical", "full-month"),
        default="historical",
        help="historical excludes the last day; full-month includes it (default: historical)",
    )
    parser.add_argument("--tiles-json", type=Path, help="JSON object mapping tile IDs to bounding boxes")
    parser.add_argument(
        "--tile-id",
        action="append",
        default=[],
        help="tile to select from JSON, or a JAXA subtile ID to derive directly; repeatable",
    )
    parser.add_argument("--crop-mask-asset", default=DEFAULT_CROP_MASK_ASSET)
    parser.add_argument("--project", help="Google Cloud project; required only with --submit")
    parser.add_argument("--output-folder", default=default_output_folder)
    parser.add_argument("--scale", type=int, default=DEFAULT_SCALE)
    parser.add_argument("--crs", default=DEFAULT_CRS)
    execution = parser.add_mutually_exclusive_group()
    execution.add_argument(
        "--submit",
        action="store_true",
        help="initialize Earth Engine and start Drive export tasks",
    )
    execution.add_argument(
        "--dry-run",
        action="store_true",
        help="print the export plan without importing Earth Engine (the default)",
    )


def config_from_args(args: argparse.Namespace) -> ExtractionConfig:
    """Build and validate the common immutable configuration."""

    if args.scale <= 0:
        raise ValueError("--scale must be positive")
    if not args.output_folder.strip():
        raise ValueError("--output-folder must not be empty")
    if not args.crop_mask_asset.strip():
        raise ValueError("--crop-mask-asset must not be empty")
    if not args.crs.strip():
        raise ValueError("--crs must not be empty")
    windows = month_windows(args.start_month, args.end_month, args.date_mode)
    if not windows:
        raise ValueError("the requested date range has no months")
    return ExtractionConfig(
        start_month=args.start_month,
        end_month=args.end_month,
        output_folder=args.output_folder.strip(),
        crop_mask_asset=args.crop_mask_asset.strip(),
        project=args.project.strip() if args.project else None,
        tiles_json=args.tiles_json,
        tile_ids=tuple(args.tile_id),
        date_mode=args.date_mode,
        scale=args.scale,
        crs=args.crs.strip(),
    )


def plan_dict(
    workflow: str,
    config: ExtractionConfig,
    tiles: Mapping[str, Sequence[float]],
    *,
    datasets: Sequence[str],
    output_bands: Sequence[str],
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a stable JSON-serializable dry-run plan."""

    windows = month_windows(config.start_month, config.end_month, config.date_mode)
    plan: dict[str, object] = {
        "mode": "dry-run",
        "workflow": workflow,
        "project": config.project,
        "tiles": list(tiles),
        "tile_count": len(tiles),
        "month_windows": [
            {"month": month, "start": start, "exclusive_end": end}
            for month, start, end in windows
        ],
        "task_count": len(tiles) * len(windows),
        "date_mode": config.date_mode,
        "crop_mask_asset": config.crop_mask_asset,
        "datasets": list(datasets),
        "output_bands": list(output_bands),
        "output_folder": config.output_folder,
        "scale": config.scale,
        "crs": config.crs,
    }
    if extra:
        plan.update(extra)
    return plan


def print_plan(plan: Mapping[str, object]) -> None:
    print(json.dumps(plan, indent=2, sort_keys=True))


def rice_mask(ee: Any, asset: str, roi: Any) -> Any:
    """Return the historical JAXA Vietnam class-3 rice mask."""

    return (
        ee.Image(asset)
        .clip(roi)
        .reproject(crs=DEFAULT_CRS, scale=10)
        .select("b1")
        .eq(3)
    )


def sample_with_coordinates(
    ee: Any,
    image: Any,
    roi: Any,
    *,
    timestamp: str,
    scale: int,
    crs: str,
) -> Any:
    """Sample an image and add the historical timestamp/lon/lat columns."""

    sampled = image.sample(
        factor=1,
        region=roi,
        geometries=True,
        scale=scale,
        projection=crs,
    )

    def add_coordinates(feature: Any) -> Any:
        coordinates = feature.geometry().coordinates()
        return feature.set(
            {
                "Timestamp": timestamp,
                "lon": coordinates.get(0),
                "lat": coordinates.get(1),
            }
        )

    return sampled.map(add_coordinates)


def start_drive_csv_export(
    ee: Any,
    collection: Any,
    *,
    description: str,
    output_folder: str,
    selectors: Iterable[str],
) -> Any:
    """Start one explicitly requested Earth Engine Drive CSV export."""

    task = ee.batch.Export.table.toDrive(
        collection=collection,
        description=description,
        folder=output_folder,
        fileFormat="CSV",
        selectors=list(selectors),
    )
    task.start()
    return task
