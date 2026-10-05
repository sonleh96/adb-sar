"""Extract historical Sentinel-1 rice RVI and optional SAR statistics.

Provenance: the default RVI-only workflow translates
``process_datasets.ipynb`` cells 13 and 15 (one-based). Optional SAR summary
bands translate the later statistics in cells 34 and 35 while retaining the
rice mask. Both modes use linear ``COPERNICUS/S1_GRD_FLOAT`` VV/VH, Sentinel-1A
descending IW scenes at 10 m, a mono-temporal 3-pixel LEE SIGMA filter, and
VOLUME SRTM terrain flattening. Historical border-noise correction was disabled
and is not applied here.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from typing import Any

from .common import (
    add_common_arguments,
    config_from_args,
    init_ee,
    month_windows,
    plan_dict,
    print_plan,
    resolve_tiles,
    rice_mask,
    sample_with_coordinates,
    start_drive_csv_export,
)
from .config import ExtractionConfig


DATASETS = ("COPERNICUS/S1_GRD_FLOAT", "USGS/SRTMGL1_003")
CORE_BANDS = ("RVI_mean",)
SAR_STATS_BANDS = (
    "RVI_mean",
    "RVI_min",
    "RVI_max",
    "VV_mean",
    "VV_min",
    "VV_max",
    "VH_mean",
    "VH_min",
    "VH_max",
    "VVVH_mean",
    "VVVH_min",
    "VVVH_max",
    "VHVV_mean",
    "VHVV_min",
    "VHVV_max",
)


def rvi_value(vv: float, vh: float) -> float:
    """Evaluate the historical linear-power RVI expression locally."""

    denominator = vv + vh
    if denominator == 0:
        raise ZeroDivisionError("RVI is undefined when VV + VH is zero")
    return 4.0 * vh / denominator


def _load_processors() -> tuple[Any, Any]:
    """Import vendored Earth Engine algorithms only on the submit path."""

    try:
        from .vendor.gee_s1_ard import speckle_filter, terrain_flattening
    except ImportError as exc:
        raise RuntimeError(
            "vendored gee_s1_ard speckle_filter.py and terrain_flattening.py are "
            "required for RVI submission"
        ) from exc
    return speckle_filter, terrain_flattening


def _rvi(image: Any) -> Any:
    return (
        image.select("VH")
        .multiply(4)
        .divide(image.select("VV").add(image.select("VH")))
        .rename("RVI")
    )


def _vvvh(image: Any) -> Any:
    return image.select("VV").divide(image.select("VH")).rename("VVVH")


def _vhvv(image: Any) -> Any:
    return image.select("VH").divide(image.select("VV")).rename("VHVV")


def _summary(collection: Any, band: str, output_prefix: str) -> Any:
    selected = collection.select(band)
    return (
        selected.mean()
        .rename(f"{output_prefix}_mean")
        .addBands(selected.min().rename(f"{output_prefix}_min"))
        .addBands(selected.max().rename(f"{output_prefix}_max"))
    )


def build_month_image(
    ee: Any,
    config: ExtractionConfig,
    roi: Any,
    mask: Any,
    *,
    start: str,
    exclusive_end: str,
    include_sar_stats: bool,
) -> Any:
    """Build a filtered and terrain-corrected RVI image for one month."""

    speckle_filter, terrain_flattening = _load_processors()
    source = (
        ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT")
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.eq("resolution_meters", 10))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.eq("platform_number", "A"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
        .filterDate(start, exclusive_end)
        .select(["VV", "VH", "angle"])
    )
    filtered = ee.ImageCollection(
        speckle_filter.MonoTemporal_Filter(source, 3, "LEE SIGMA")
    )
    corrected = terrain_flattening.slope_correction(
        filtered,
        "VOLUME",
        ee.Image("USGS/SRTMGL1_003"),
        0,
    )

    rvi = corrected.map(_rvi)
    if include_sar_stats:
        image = _summary(rvi, "RVI", "RVI")
        image = image.addBands(_summary(corrected, "VV", "VV"))
        image = image.addBands(_summary(corrected, "VH", "VH"))
        image = image.addBands(_summary(corrected.map(_vvvh), "VVVH", "VVVH"))
        image = image.addBands(_summary(corrected.map(_vhvv), "VHVV", "VHVV"))
    else:
        image = rvi.mean().rename("RVI_mean")
    return image.updateMask(mask).reproject(crs=config.crs, scale=config.scale).clip(roi)


def submit_exports(
    ee: Any,
    config: ExtractionConfig,
    tiles: Mapping[str, Sequence[float]],
    *,
    include_sar_stats: bool,
) -> list[Any]:
    bands = SAR_STATS_BANDS if include_sar_stats else CORE_BANDS
    selectors = ("Timestamp", "lon", "lat", *bands)
    tasks: list[Any] = []
    for tile_id, bbox in tiles.items():
        roi = ee.Geometry.BBox(*bbox)
        mask = rice_mask(ee, config.crop_mask_asset, roi)
        for _month, start, exclusive_end in month_windows(
            config.start_month, config.end_month, config.date_mode
        ):
            image = build_month_image(
                ee,
                config,
                roi,
                mask,
                start=start,
                exclusive_end=exclusive_end,
                include_sar_stats=include_sar_stats,
            )
            features = sample_with_coordinates(
                ee,
                image,
                roi,
                timestamp=start,
                scale=config.scale,
                crs=config.crs,
            )
            suffix = "_sar_stats" if include_sar_stats else ""
            description = f"{tile_id}_{config.scale}m_{start}{suffix}"
            tasks.append(
                start_drive_csv_export(
                    ee,
                    features,
                    description=description,
                    output_folder=config.output_folder,
                    selectors=selectors,
                )
            )
            print(f"submitted {description}")
    return tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser, default_output_folder="rice_rvi")
    parser.add_argument(
        "--include-sar-stats",
        action="store_true",
        help="also export RVI/VV/VH/VV-VH ratio monthly mean, min, and max bands",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        tiles = resolve_tiles(config.tiles_json, config.tile_ids)
    except ValueError as exc:
        parser.error(str(exc))
    bands = SAR_STATS_BANDS if args.include_sar_stats else CORE_BANDS
    if not args.submit:
        print_plan(
            plan_dict(
                "rvi",
                config,
                tiles,
                datasets=DATASETS,
                output_bands=bands,
                extra={
                    "formula": "4 * VH / (VV + VH), using linear GRD_FLOAT bands",
                    "sentinel1_filters": {
                        "instrument_mode": "IW",
                        "resolution_meters": 10,
                        "platform_number": "A",
                        "orbit": "DESCENDING",
                        "polarizations": ["VV", "VH"],
                    },
                    "speckle_filter": "MonoTemporal LEE SIGMA, kernel size 3",
                    "terrain_flattening": "VOLUME with USGS/SRTMGL1_003",
                    "include_sar_stats": args.include_sar_stats,
                },
            )
        )
        return 0
    if not config.project:
        parser.error("--project is required with --submit")
    ee = init_ee(config.project or "")
    submit_exports(ee, config, tiles, include_sar_stats=args.include_sar_stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
