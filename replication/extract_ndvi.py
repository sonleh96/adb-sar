"""Extract historical monthly rice NDVI summaries to Drive CSV files.

Provenance: translated from the rice workflow in ``process_datasets.ipynb``
cells 29 and 30, using the ``getNDVI`` definition in cell 24 (one-based). It
intentionally uses unmasked Sentinel-2 Harmonized Level-1C imagery, B8 and B4,
and the JAXA Vietnam class-3 rice mask. No cloud or quality mask is added.
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


DATASETS = ("COPERNICUS/S2_HARMONIZED",)
OUTPUT_BANDS = ("NDVI_mean", "NDVI_min", "NDVI_max")
SELECTORS = ("Timestamp", "lon", "lat", *OUTPUT_BANDS)


def ndvi_value(nir: float, red: float) -> float:
    """Return ``(NIR - red) / (NIR + red)`` for a local numeric check."""

    denominator = nir + red
    if denominator == 0:
        raise ZeroDivisionError("NDVI is undefined when NIR + red is zero")
    return (nir - red) / denominator


def build_month_image(
    ee: Any,
    config: ExtractionConfig,
    roi: Any,
    mask: Any,
    *,
    start: str,
    exclusive_end: str,
) -> Any:
    """Build the historical mean/min/max NDVI band stack."""

    def mask_and_calculate(image: Any) -> Any:
        return image.updateMask(mask).normalizedDifference(["B8", "B4"]).rename("NDVI")

    collection = (
        ee.ImageCollection("COPERNICUS/S2_HARMONIZED")
        .filterDate(start, exclusive_end)
        .map(mask_and_calculate)
    )
    mean = collection.mean().rename("NDVI_mean").reproject(crs=config.crs, scale=config.scale)
    minimum = collection.min().rename("NDVI_min").reproject(crs=config.crs, scale=config.scale)
    maximum = collection.max().rename("NDVI_max").reproject(crs=config.crs, scale=config.scale)
    return mean.addBands(minimum).addBands(maximum)


def submit_exports(
    ee: Any,
    config: ExtractionConfig,
    tiles: Mapping[str, Sequence[float]],
) -> list[Any]:
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
            )
            features = sample_with_coordinates(
                ee,
                image,
                roi,
                timestamp=start,
                scale=config.scale,
                crs=config.crs,
            )
            description = f"{tile_id}_{config.scale}m_{start}"
            tasks.append(
                start_drive_csv_export(
                    ee,
                    features,
                    description=description,
                    output_folder=config.output_folder,
                    selectors=SELECTORS,
                )
            )
            print(f"submitted {description}")
    return tasks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_common_arguments(parser, default_output_folder="rice_ndvi")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        tiles = resolve_tiles(config.tiles_json, config.tile_ids)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.submit:
        print_plan(
            plan_dict(
                "ndvi",
                config,
                tiles,
                datasets=DATASETS,
                output_bands=OUTPUT_BANDS,
                extra={
                    "sentinel2_processing": "Level-1C harmonized, no cloud mask",
                    "formula": "(B8 - B4) / (B8 + B4)",
                },
            )
        )
        return 0
    if not config.project:
        parser.error("--project is required with --submit")
    ee = init_ee(config.project or "")
    submit_exports(ee, config, tiles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
