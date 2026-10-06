"""Extract ESI and Aqua FPAR for the manuscript.

Provenance: translated from ``extract_channels.ipynb`` cell 5 (one-based).
The code preserves the historical ESI 4-week and MCD15A3H Aqua FPAR logic,
including the not-produced SCF_QC exclusion and FPAR scale factor.
ET, soil moisture, and Terra FPAR are excluded from the image stack, so their
masks do not determine which ESI/Aqua samples are retained.
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


DATASETS = (
    "projects/climate-engine/esi/4wk",
    "MODIS/061/MCD15A3H",
)
OUTPUT_BANDS = (
    "ESI_4wk_mean",
    "ESI_4wk_min",
    "ESI_4wk_max",
    "FPAR_Aqua_mean",
    "FPAR_Aqua_min",
    "FPAR_Aqua_max",
)
SELECTORS = ("Timestamp", "lon", "lat", *OUTPUT_BANDS)


def extract_bits_value(value: int, bit_start: int, bit_end: int) -> int:
    """Extract an inclusive bit range for local verification of the QC rule."""

    if bit_start < 0 or bit_end < bit_start:
        raise ValueError("bit positions must satisfy 0 <= bit_start <= bit_end")
    return (value >> bit_start) & ((1 << (bit_end - bit_start + 1)) - 1)


def fpar_qc_accepts(value: int) -> bool:
    """Check the historical Aqua FPAR QC rule locally without Earth Engine."""

    return extract_bits_value(value, 5, 7) != 4 and extract_bits_value(value, 1, 1) == 1


def _project(image: Any, roi: Any, config: ExtractionConfig) -> Any:
    return image.reproject(crs=config.crs, scale=config.scale).clip(roi)


def _stats(
    collection: Any,
    source_band: str,
    output_prefix: str,
    roi: Any,
    config: ExtractionConfig,
    *,
    scale_factor: float | None = None,
) -> Any:
    def finish(image: Any, suffix: str) -> Any:
        if scale_factor is not None:
            image = image.multiply(scale_factor)
        return _project(image.rename(f"{output_prefix}_{suffix}"), roi, config)

    selected = collection.select(source_band)
    return (
        finish(selected.mean(), "mean")
        .addBands(finish(selected.min(), "min"))
        .addBands(finish(selected.max(), "max"))
    )


def build_month_image(
    ee: Any,
    config: ExtractionConfig,
    roi: Any,
    mask: Any,
    *,
    start: str,
    exclusive_end: str,
) -> Any:
    """Build the ESI and Aqua FPAR stack for one tile-month."""

    def mask_crop(image: Any) -> Any:
        return image.updateMask(mask)

    esi = (
        ee.ImageCollection("projects/climate-engine/esi/4wk")
        .filterDate(start, exclusive_end)
        .map(mask_crop)
    )
    esi_stats = _stats(esi, "ESI", "ESI_4wk", roi, config)

    fpar = (
        ee.ImageCollection("MODIS/061/MCD15A3H")
        .filterDate(start, exclusive_end)
        .map(mask_crop)
    )

    def extract_bits(image: Any, bit_start: int, bit_end: int) -> Any:
        return image.rightShift(bit_start).bitwiseAnd((1 << (bit_end - bit_start + 1)) - 1)

    def mask_aqua(image: Any) -> Any:
        qc = image.select("FparLai_QC")
        scf_qc = extract_bits(qc, 5, 7).neq(4)
        sensor = extract_bits(qc, 1, 1).eq(1)
        return image.updateMask(scf_qc.And(sensor))

    aqua = fpar.map(mask_aqua)
    aqua_stats = _stats(
        aqua,
        "Fpar",
        "FPAR_Aqua",
        roi,
        config,
        scale_factor=0.01,
    )
    return esi_stats.addBands(aqua_stats)


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
            description = f"{tile_id}_{config.scale}m_{start}_rice"
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
    add_common_arguments(parser, default_output_folder="rice_channels")
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
                "esi-aqua-fpar",
                config,
                tiles,
                datasets=DATASETS,
                output_bands=OUTPUT_BANDS,
                extra={
                    "fpar_scale_factor": 0.01,
                    "fpar_qc": "SCF_QC bits 5-7 != 4 and sensor bit 1 == 1 (Aqua)",
                    "sample_mask": "joint validity of ESI and Aqua FPAR only",
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
