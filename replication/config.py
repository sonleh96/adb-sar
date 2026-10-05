"""Shared configuration defaults for the historical extraction workflows.

The defaults identify private historical inputs referenced by
``process_datasets.ipynb``. They make the provenance visible but do not imply
that those assets are public or independently rebuildable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_CRS = "EPSG:4326"
DEFAULT_SCALE = 100
DEFAULT_CROP_MASK_ASSET = "projects/ee-sonle96/assets/LULC_VN"
DEFAULT_NTL_ASSET_PREFIX = "projects/ee-sonle96/assets/BM_VN_processed"


@dataclass(frozen=True)
class ExtractionConfig:
    """Portable settings shared by an Earth Engine extraction command."""

    start_month: str
    end_month: str
    output_folder: str
    crop_mask_asset: str = DEFAULT_CROP_MASK_ASSET
    project: str | None = None
    tiles_json: Path | None = None
    tile_ids: tuple[str, ...] = ()
    date_mode: str = "historical"
    scale: int = DEFAULT_SCALE
    crs: str = DEFAULT_CRS
