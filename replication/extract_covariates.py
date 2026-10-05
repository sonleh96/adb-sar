"""Extract historical environmental covariates to Google Drive CSV files.

Provenance: translated from ``process_datasets.ipynb`` cells 13 and 15
(one-based). The implementation preserves the literal RVI-first combined stack,
CAMS NRT PM2.5 scaling, ERA5-Land monthly reducers and fractional Magnus
relative humidity, Sentinel-5P gases, wind, precipitation, elevation, and the
private preprocessed monthly Black Marble ``b1`` inputs. It does not reconstruct
the unavailable Black Marble upstream preprocessing.
"""

from __future__ import annotations

import argparse
import math
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
from .config import DEFAULT_NTL_ASSET_PREFIX, ExtractionConfig
from .extract_rvi import build_month_image as build_rvi_month_image


DATASETS = (
    "COPERNICUS/S1_GRD_FLOAT",
    "ECMWF/CAMS/NRT",
    "COPERNICUS/S5P/OFFL/L3_NO2",
    "COPERNICUS/S5P/OFFL/L3_O3",
    "ECMWF/ERA5_LAND/DAILY_AGGR",
    "USGS/SRTMGL1_003",
)
OUTPUT_BANDS = (
    "RVI_mean",
    "PM25_mean",
    "PM25_max",
    "NO2_mean",
    "NO2_max",
    "O3_mean",
    "O3_max",
    "Temperature_mean",
    "Temperature_max",
    "Wind_speed_mean",
    "Wind_speed_max",
    "Rel_humidity_mean",
    "Precipitation_sum",
    "Luminosity",
    "elevation",
)
SELECTORS = ("Timestamp", "lon", "lat", "CropType", "Country", *OUTPUT_BANDS)


def relative_humidity_fraction(
    temperature_c: float,
    dewpoint_c: float,
    *,
    b: float = 17.625,
    c: float = 243.04,
) -> float:
    """Evaluate the notebook's Magnus relative-humidity expression."""

    numerator = (dewpoint_c - temperature_c) * c * b
    denominator = (temperature_c + c) * (dewpoint_c + c)
    return math.exp(numerator / denominator)


def _project(image: Any, roi: Any, config: ExtractionConfig) -> Any:
    return image.clip(roi).reproject(crs=config.crs, scale=config.scale)


def build_month_image(
    ee: Any,
    config: ExtractionConfig,
    roi: Any,
    mask: Any,
    *,
    month: str,
    start: str,
    exclusive_end: str,
    ntl_asset_prefix: str,
) -> Any:
    """Build the cell-15 covariate stack for one tile-month."""

    def mask_crop(image: Any) -> Any:
        return image.updateMask(mask)

    rvi = build_rvi_month_image(
        ee,
        config,
        roi,
        mask,
        start=start,
        exclusive_end=exclusive_end,
        include_sar_stats=False,
    )

    pm25 = ee.ImageCollection("ECMWF/CAMS/NRT").filterDate(start, exclusive_end).map(mask_crop)
    pm25_mean = _project(
        pm25.select("particulate_matter_d_less_than_25_um_surface")
        .mean()
        .multiply(1e9)
        .rename("PM25_mean"),
        roi,
        config,
    )
    pm25_max = _project(
        pm25.select("particulate_matter_d_less_than_25_um_surface")
        .max()
        .multiply(1e9)
        .rename("PM25_max"),
        roi,
        config,
    )

    no2 = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_NO2")
        .filterDate(start, exclusive_end)
        .map(mask_crop)
        .filterBounds(roi)
    )
    no2_mean = _project(
        no2.select("NO2_column_number_density").mean().rename("NO2_mean"), roi, config
    )
    no2_max = _project(
        no2.select("NO2_column_number_density").max().rename("NO2_max"), roi, config
    )

    o3 = (
        ee.ImageCollection("COPERNICUS/S5P/OFFL/L3_O3")
        .filterDate(start, exclusive_end)
        .map(mask_crop)
        .filterBounds(roi)
    )
    o3_mean = _project(
        o3.select("O3_column_number_density").mean().rename("O3_mean"), roi, config
    )
    o3_max = _project(
        o3.select("O3_column_number_density").max().rename("O3_max"), roi, config
    )

    era5 = (
        ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
        .filterDate(start, exclusive_end)
        .map(mask_crop)
    )
    mean_temp = _project(
        era5.select("temperature_2m").mean().subtract(273.15).rename("Temperature_mean"),
        roi,
        config,
    )
    max_temp = _project(
        era5.select("temperature_2m").max().subtract(273.15).rename("Temperature_max"),
        roi,
        config,
    )

    mean_wind_u = era5.select("u_component_of_wind_10m").mean()
    mean_wind_v = era5.select("v_component_of_wind_10m").mean()
    mean_wind_speed = _project(
        mean_wind_u.multiply(mean_wind_u)
        .add(mean_wind_v.multiply(mean_wind_v))
        .sqrt()
        .rename("Wind_speed_mean"),
        roi,
        config,
    )
    max_wind_u = era5.select("u_component_of_wind_10m").max()
    max_wind_v = era5.select("v_component_of_wind_10m").max()
    max_wind_speed = _project(
        max_wind_u.multiply(max_wind_u)
        .add(max_wind_v.multiply(max_wind_v))
        .sqrt()
        .rename("Wind_speed_max"),
        roi,
        config,
    )
    precipitation = _project(
        era5.select("total_precipitation_sum").sum().rename("Precipitation_sum"),
        roi,
        config,
    )

    mean_dewpoint = _project(
        era5.select("dewpoint_temperature_2m")
        .mean()
        .subtract(273.15)
        .rename("avg_dew_temperature"),
        roi,
        config,
    )
    b = 17.625
    c = 243.04
    numerator = mean_dewpoint.subtract(mean_temp).multiply(c).multiply(b)
    denominator = mean_temp.add(c).multiply(mean_dewpoint.add(c))
    mean_humidity = numerator.divide(denominator).exp().rename("Rel_humidity_mean")

    ntl_asset = f"{ntl_asset_prefix.rstrip('/')}/VNM_bm_{month.replace('-', '_')}"
    luminosity = _project(
        ee.Image(ntl_asset).select("b1").rename("Luminosity").updateMask(mask),
        roi,
        config,
    )
    elevation = _project(
        ee.Image("USGS/SRTMGL1_003")
        .select("elevation")
        .updateMask(mask)
        .rename("elevation"),
        roi,
        config,
    )

    return (
        rvi.addBands(pm25_mean)
        .addBands(pm25_max)
        .addBands(no2_mean)
        .addBands(no2_max)
        .addBands(o3_mean)
        .addBands(o3_max)
        .addBands(mean_temp)
        .addBands(max_temp)
        .addBands(mean_wind_speed)
        .addBands(max_wind_speed)
        .addBands(mean_humidity)
        .addBands(precipitation)
        .addBands(luminosity)
        .addBands(elevation)
    )


def submit_exports(
    ee: Any,
    config: ExtractionConfig,
    tiles: Mapping[str, Sequence[float]],
    *,
    ntl_asset_prefix: str,
) -> list[Any]:
    """Build and start one Drive task per requested tile-month."""

    tasks: list[Any] = []
    for tile_id, bbox in tiles.items():
        roi = ee.Geometry.BBox(*bbox).bounds(proj=config.crs)
        mask = rice_mask(ee, config.crop_mask_asset, roi)
        for month, start, exclusive_end in month_windows(
            config.start_month, config.end_month, config.date_mode
        ):
            image = build_month_image(
                ee,
                config,
                roi,
                mask,
                month=month,
                start=start,
                exclusive_end=exclusive_end,
                ntl_asset_prefix=ntl_asset_prefix,
            )
            features = sample_with_coordinates(
                ee,
                image,
                roi,
                timestamp=start,
                scale=config.scale,
                crs=config.crs,
            )

            def add_context(feature: Any) -> Any:
                return feature.set({"CropType": "Rice", "Country": "VN"})

            features = features.map(add_context)
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
    add_common_arguments(parser, default_output_folder="rice_covariates")
    parser.add_argument(
        "--ntl-asset-prefix",
        default=DEFAULT_NTL_ASSET_PREFIX,
        help="prefix containing VNM_bm_YYYY_MM preprocessed Black Marble images",
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
    ntl_asset_prefix = args.ntl_asset_prefix.strip()
    if not ntl_asset_prefix:
        parser.error("--ntl-asset-prefix must not be empty")
    if not args.submit:
        print_plan(
            plan_dict(
                "covariates",
                config,
                tiles,
                datasets=(*DATASETS, f"{ntl_asset_prefix.rstrip('/')}/VNM_bm_YYYY_MM"),
                output_bands=OUTPUT_BANDS,
                extra={
                    "ntl_asset_prefix": ntl_asset_prefix,
                    "sample_drop_nulls": True,
                    "stack_mode": "literal process_datasets.ipynb cell 15",
                    "limitations": [
                        "The nighttime-light inputs are private preprocessed assets.",
                        "Their upstream Black Marble preprocessing is not present in the source repository.",
                        "The literal cell-15 stack includes Sentinel-5P collections whose coverage starts in 2018.",
                        "Sampling retains Earth Engine's default dropNulls behavior, so early or missing bands can produce no rows.",
                        "The source review does not establish this literal stack as exact provenance for the delivered CSV.",
                    ],
                },
            )
        )
        return 0
    if not config.project:
        parser.error("--project is required with --submit")
    ee = init_ee(config.project or "")
    submit_exports(ee, config, tiles, ntl_asset_prefix=ntl_asset_prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
