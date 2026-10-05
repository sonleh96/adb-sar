# Satellite extraction preparation release

This package translates the available satellite and environmental extraction code into ordinary Python scripts.
It covers NDVI, Sentinel-1 RVI, CAMS PM2.5, ERA5-Land temperature and humidity, consumption of preprocessed nighttime lights, and two distinct historical fire workflows.
Optional modules cover ESI, soil moisture, FPAR, evapotranspiration, JAXA tile definitions, and rice calendar sampling.
The code archive contains this README and Python files only.

This is a preparation release, not a verified reproduction of all values in `SAR_SVN_rice_reprod.csv`.
Nighttime lights preprocessing has not been recovered, the historical PM2.5 and fire sources remain to be confirmed, and live extraction requires renewed Earth Engine authentication and access to the custom inputs.
There is no Zenodo DOI for this package yet.

Son's contribution ends at the extraction data delivered to Eugenia, including `SAR_SVN_rice_reprod.csv`.
Eugenia's later preparation of analysis or training datasets, Stata results, crop and drought classifications, and figures belongs to her analysis replication contribution.
These scripts do not reconstruct those later steps or assert that concatenating exports recreates the delivered CSV.
The delivered CSV already contains additional derived fields, including `av_*`, plot identifiers, and lags; their pre-handoff construction is not established by the extraction scripts reviewed here.
Responsibility for any missing pre-handoff transformations must be confirmed rather than automatically assigned to Eugenia.

Contact: Son Le, sonle.h96@gmail.com.
GitHub: [sonleh96/adb-sar](https://github.com/sonleh96/adb-sar).
Historical parent revision reviewed: `c2766214c17e47cac94dc441c8e5353f1ee6931f`.
The original notebooks are retained in the repository as historical source material and are not required by the Python workflow or included in this archive.
Cell references below count all notebook cells, starting at one.

## Files and provenance

| Python module | Purpose | Historical source |
| --- | --- | --- |
| `config.py`, `common.py` | Configuration, monthly bounds, tiles, rice masks, sampling, and exports | `process_datasets.ipynb`, cells 13, 15, 29-30 |
| `extract_covariates.py` | Original combined RVI, CAMS, meteorology, gases, NTL, and elevation stack | `process_datasets.ipynb`, cells 13 and 15 |
| `extract_ndvi.py` | Monthly rice NDVI mean, minimum, and maximum | `process_datasets.ipynb`, cells 24, 29-30 |
| `extract_rvi.py` | RVI, with optional additional SAR summaries | `process_datasets.ipynb`, cells 13, 15, 34-35 |
| `extract_fire.py` | Administrative MODIS FRP statistics or separate FIRMS T21 statistics | `docs/analysis/frp.ipynb`, cells 13-14; `process_datasets.ipynb`, cell 20 |
| `extract_channels.py` | Optional ESI, ET, soil moisture, and FPAR statistics | `extract_channels.ipynb`, cell 5 |
| `prepare_inputs.py` | JAXA raster metadata to subtile bounds | `split_jaxa_tiles.ipynb` |
| `prepare_fire_distances.py` | Administrative centroid distance to the selected southern Vietnam tile union | `docs/analysis/frp.ipynb`, cells 5-11 |
| `prepare_calendar.py` | Historical rice harvest calendar raster conversion and coordinate sampling | `extract_channels.ipynb`, cells 30-31, 42-48 |
| `assemble_outputs.py` | Streaming CSV concatenation and flat fire JSON-to-CSV conversion | Portable helper; fire conversion follows the concatenation in `docs/analysis/frp.ipynb`, cell 17 |
| `validate_sample.py` | Offline method checks, bounded CSV inspection, and supplied-sample comparison | New validation helper |
| `build_release.py` | Deterministic code-only ZIP and checksum inventory | New packaging helper |
| `vendor/gee_s1_ard/*.py` | Historical Sentinel-1 filtering and terrain correction | Upstream revision `b50430bd9b2b00e1392532202b88ded6c416932a` |

The optional SAR summaries use statistics from a later wheat branch with the rice mask explicitly selected here.
Their inclusion does not establish that the same branch generated the rice handoff's `vv`, `vh`, and `vvvh` columns.
The new concatenation helper preserves CSV text values rather than reproducing the exploratory notebook's `float16` casting.

## Environment

Use Python 3.11 or newer.
Command-line help, dry runs, CSV assembly, validation, and packaging use the standard library.
Earth Engine execution additionally needs `earthengine-api`.
JAXA raster preparation and calendar processing additionally need `rasterio`, `numpy`, `xarray`, and a NetCDF backend such as `scipy`.
Fire-distance preparation additionally needs `shapely` and `pyproj`.

The local checks used Python 3.11.11, `earthengine-api==0.1.401`, `numpy==1.26.4`, `xarray==2023.6.0`, `scipy==1.11.4`, `rasterio==1.4.3`, and `affine==2.4.0`.
The fire-distance comparison used `shapely==2.0.6` and `pyproj==3.6.1`.
Pin `affine==2.4.0` with this environment: version 3.0.1 failed while reading a real JAXA raster's transform under Python 3.11.
Those versions document the checked environment; successful offline tests do not establish current remote product access.
Neither `geemap` nor Jupyter is required.

From a fresh environment, install the optional execution dependencies as needed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install earthengine-api==0.1.401 numpy==1.26.4 xarray==2023.6.0 scipy==1.11.4 rasterio==1.4.3 affine==2.4.0 shapely==2.0.6 pyproj==3.6.1
```

Keep credentials outside the code directory.
Authenticate separately using `earthengine authenticate`, select your own registered Google Cloud project, and ensure that account can read every requested custom asset.
The scripts never launch an interactive authentication flow themselves.
The historical asset names identify inputs; they do not grant access to another user's assets.
See the official [Earth Engine authentication guide](https://developers.google.com/earth-engine/guides/auth).

## Required inputs

1. Select the exact historical tile definitions or derive a new JSON mapping from the original JAXA raster metadata.
   The local sources include `shapefiles/JAXA_subtiles.json` and `JAXA_subtiles_full.json`; their precise paper subset still needs confirmation.
   The JSON format is a mapping from a tile ID to `[west, south, east, north]` in EPSG:4326.
   A direct `--tile-id N10E105_0_1` also supports planning using the nominal half-degree JAXA subtile convention.
   Raster-derived bounds should be used for the historical validation when exact coordinates matter.
2. Supply an Earth Engine crop-mask image with band `b1` and rice class `3`.
   The historical default is `projects/ee-sonle96/assets/LULC_VN`.
   The source notebooks read a clipped JAXA mask, but the complete clipping and upload pipeline is not available in the reviewed code.
   The local raw raster filenames identify the 2020 Vietnam map, version `v23.09`, at 10 m; this is not proof that every historical run used that version.
3. Supply preprocessed monthly nighttime-light images named `VNM_bm_YYYY_MM`, each with band `b1`.
   The historical prefix is `projects/ee-sonle96/assets/BM_VN_processed`.
   The visible source uploads these rasters and reads them; it does not implement the cleaning and smoothing described in the older manuscript.
   No substitute preprocessing algorithm is included here.
4. For fire statistics, supply the relevant administrative polygons, their identifier column, and administrative level.
   The later notebook uses level 1 for Thailand and Indonesia and level 2 for other countries.
   The original FIRMS country geometry is the union of `FAO/GAUL/2015/level2` polygons filtered to Indonesia, rather than the GADM boundaries used by the later FRP branch.
   A caller-supplied FIRMS GeoJSON must reproduce that geometry for a comparable historical run; using a different boundary changes the spatial statistics.
   Regional distances do not themselves reconstruct the downstream fitted instruments.
   `prepare_fire_distances.py` projects both the selected tile union and administrative polygons to EPSG:3405, computes their centroids, and measures Euclidean distances in kilometers.
   It preserves the original administrative geometries in EPSG:4326 and adds the distance property; the old notebook's output instead contained projected centroid geometries.
   Supply the exact historical tile selection and any country or province filters explicitly.
5. For calendar processing, supply the original `1_Transplanting_Harvest_Group.nc` and `3_Transplanting_Harvest_Cropping.nc`, and a coordinate CSV with `lon` and `lat`.
   Input rasters, NetCDF files, administrative boundaries, reference CSVs, and generated outputs are separate data inputs and are not included in this code archive.

## Extraction definitions and handoff fields

The field mapping is a candidate correspondence based on visible source names and the delivered CSV header.
Confirm it against the final manuscript and historical assembly code before claiming complete provenance.

| Extraction field | Candidate handoff field | Definition and units |
| --- | --- | --- |
| `NDVI_mean` | `ndvi` | Monthly mean of `(B8-B4)/(B8+B4)` from Sentinel-2 Harmonized Level-1C; unitless |
| `RVI_mean` | `rvi` | Monthly mean of `4*VH/(VV+VH)` using linear Sentinel-1 power; unitless |
| `PM25_mean`, `PM25_max` | `pm25_mean`, `pm25_max` | CAMS NRT surface PM2.5 mean/max multiplied by `1e9`; micrograms per cubic meter |
| `Temperature_mean`, `Temperature_max` | `temp_av`, `temp_max` | Mean/max of ERA5-Land daily `temperature_2m`, minus 273.15; degrees Celsius |
| `Rel_humidity_mean` | `hum_av` | Magnus expression evaluated after separately averaging temperature and dew point; fraction, not percent |
| `Precipitation_sum` | `rain_cum` | Sum of ERA5-Land daily `total_precipitation_sum`; meters |
| `Luminosity` | `luminosity` | Preprocessed monthly custom asset `b1`; precise upstream units and transformations require confirmation |
| `ESI_4wk_mean` | `esi_4wk_mean` | Climate Engine four-week ESI monthly mean |
| `SM_ROOT_mean` | `sm_root_mean` | SMAP L4 `sm_rootzone` monthly mean; cubic meters per cubic meter |
| `FPAR_Terra_mean`, `FPAR_Aqua_mean` | `fpar_terra_mean`, `fpar_aqua_mean` | MODIS FPAR, scaled by 0.01, with the historical QC and sensor-bit masks |
| `MaxFRP_*_*` | To be confirmed | Temporal mean/max or historical minimum alias, followed by spatial mean/max/min; MW |
| `Mean_T21`, `Max_T21` | To be confirmed | Separate FIRMS T21 brightness-temperature series; kelvin |

Relative humidity uses `exp((Td-T)*243.04*17.625 / ((T+243.04)*(Td+243.04)))` with monthly mean `T` and `Td` in degrees Celsius.
This is not the mean of daily relative humidity.
Wind speed is computed from monthly component summaries, not the mean or maximum of daily vector magnitudes.
The minimum and maximum temperature fields aggregate the daily mean temperature band, not the separate ERA5 daily minimum and maximum bands.

NDVI uses `COPERNICUS/S2_HARMONIZED`, which the official catalog identifies as [Level-1C top-of-atmosphere reflectance](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_HARMONIZED).
The historical rice branch adds no cloud-quality mask and is preserved here.
RVI uses Sentinel-1A descending IW scenes with both VV and VH, the actual mono-temporal Lee Sigma filter with kernel 3, and VOLUME terrain flattening using SRTM with zero additional buffer.
The notebook's unused multi-temporal configuration labels are not used to describe that executed filter.
Optional channels use SMAP rather than GLDAS; the manuscript source description must be reconciled separately.

The default sampling is EPSG:4326 at 100 m, with the 10 m class-3 rice mask and Earth Engine's default nearest-neighbor resampling.
This output grid does not imply that CAMS, ERA5, NTL, or other coarse input products have native 100 m information.
Sampling drops pixels with a null value in any sampled band.
The combined covariates stack therefore preserves the original RVI and Sentinel-5P gases even though they extend beyond the seven requested variables.
Sentinel-5P coverage starts after the initial 2017 extraction dates, so that literal combined branch cannot establish the origin of the nonempty 2017 handoff rows.
Standalone NDVI, RVI, and channel exports have their own joint validity masks and may have different coordinate sets.

Earth Engine date ends are [exclusive](https://developers.google.com/earth-engine/apidocs/ee-imagecollection-filterdate).
The default `--date-mode historical` passes the last calendar day as the exclusive end, reproducing the notebook's omission of that day's observations.
`--date-mode full-month` uses the first day of the next month and changes the extracted data.
Do not substitute corrected date bounds for historical outputs without a real comparison and agreement with the manuscript authors.

The historical FRP branch assigns its temporal `MaxFRP_min` band using `.max()`.
Historical mode keeps this alias; the explicitly corrected mode uses `.min()` and changes results.
FRP is scaled by 0.1 as specified for [MOD14A1 MaxFRP](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD14A1).
The source quality rule retains FireMask low bits at least 7 and QA land/water low bits at most 2.
FIRMS T21 and MODIS FRP are distinct quantities and must not be treated as interchangeable fire measurements.

## Execution

Run the modules from the directory containing `replication/`.
After unzipping a code archive, its top-level `replication/` directory serves the same purpose.

Start with one tile and one month, using a dry run:

```powershell
python -m replication.extract_ndvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_rvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_channels --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

Dry runs print the requested products, dates, settings, and task count without importing Earth Engine or starting exports.
Use `--tiles-json PATH --tile-id ID` to select a historical tile from an external mapping; repeat `--tile-id` for additional tiles.
Omitting `--tile-id` when supplying a mapping selects every tile in that mapping.
There are no hidden positional tile slices, resume offsets, or one-month demonstration loops.

When the plan and inputs have been checked, add `--project YOUR_PROJECT --crop-mask-asset YOUR_ASSET --submit`.
For covariates, also pass `--ntl-asset-prefix YOUR_MONTHLY_ASSET_FOLDER` if using a different NTL folder.
Submission starts one Drive CSV task per selected tile-month; inspect task completion in Earth Engine and download the finished files before assembly.
A submission message means a task was started, not that the export completed successfully.
Use a distinct Drive folder for each workflow or historical/corrected run.

Run `python -m replication.extract_fire --help`, `python -m replication.prepare_inputs --help`, `python -m replication.prepare_fire_distances --help`, and `python -m replication.prepare_calendar --help` for the required local input arguments.
The fire command uses explicit regional inputs and writes regional monthly statistics separately from rice-grid exports.
Calendar month conversion retains the source's fixed 2019 convention.
Calendar raster conversion defaults to the historical transform that treats coordinate centers as outer bounds.
`--mode corrected` instead uses inferred cell edges and can change which cell is sampled.
The historical source files have ascending longitude and descending latitude; their rows do not need a latitude flip.
Calendar CSVs retain blank missing values while GeoTIFFs use `-9999` as no-data.
Calendar sampling defaults to the literal notebook convention: the dates output contains month numbers under the old `*_doy` column names.
Use `--sampling-mode corrected` to put actual day-of-year values in that output, with the same month conversion in the separate months file.
The local archived `rice_marc_harvest_dates.csv` contains raw day-of-year values, so its content differs from the visible notebook's final dates-writing cell.
The archived month CSV is the reference used for the calendar month comparison.

Examples with separately supplied inputs:

```powershell
python -m replication.prepare_inputs PATH_TO_JAXA_RASTERS --output release_outputs/tiles.json
python -m replication.prepare_calendar convert --group-netcdf GROUP.nc --cropping-netcdf CROPPING.nc --output-dir release_outputs/calendar --mode historical
python -m replication.prepare_calendar sample --raster-dir release_outputs/calendar --points small_coordinates.csv --dates-output release_outputs/harvest_dates.csv --month-output release_outputs/harvest_months.csv --sampling-mode historical
python -m replication.extract_fire --geojson IDN_ADMIN1.geojson --id-column GID_1 --country-label IDN --admin-level 1 --start-month 2019-01 --end-month 2019-01 --output-dir release_outputs/fire
python -m replication.assemble_outputs "release_outputs/fire/IDN/*.json" --json-records --key GID --key date --duplicate-check sqlite --output release_outputs/idn_frp.csv
python -m replication.assemble_outputs "DOWNLOADED_NDVI_BATCHES/*.csv" --output release_outputs/ndvi.csv --duplicate-check sqlite
```

The fire example is an offline plan; add `--project YOUR_PROJECT --submit` to request the regional values.
Use a small coordinates-only CSV for calendar sampling, rather than the complete multi-gigabyte handoff file.
CSV assembly requires identical ordered headers and retains text values.
Fire JSON conversion uses a stable union of the flat record fields, writes JSON null values as blank CSV fields, and adds no numeric precision reduction.
Keep MODIS FRP and FIRMS T21 inputs separate; T21 JSON conversion uses `--key Timestamp --key country` instead of `GID` and `date`.
Its default duplicate check covers only the first 100,000 rows; `--duplicate-check sqlite` checks all exact text keys using a temporary disk index.

## Validation and archive preparation

```powershell
python -m replication.validate_sample --self-test
python -m replication.validate_sample --csv PATH_TO_HANDOFF.csv --rows 1000
python -m replication.validate_sample --reference historical_sample.csv --candidate new_sample.csv --key Timestamp --key lon --key lat --tolerance NDVI_mean=0.00001 --rows 1000
python -m replication.validate_sample --frp-json-dir HISTORICAL_IDN_JSON_DIRECTORY --frp-csv HISTORICAL_IDN_FRP.csv --rows 50
python -m replication.build_release --output release_outputs/adb-sar-extraction-preparation.zip
```

Validation is deliberately bounded for large historical CSVs.
Use an independently supplied historical sample for value comparisons and explicit keys and tolerances appropriate to the source precision.
Inspection of the first rows checks only that sample, not complete coverage or the source of each field.
The delivered CSV contains rounded values, and the exploratory assembly code used reduced precision; exact decimal equality may therefore be inappropriate for comparisons with fresh exports.

The release builder packages only Python files and this README, checks the ZIP, and records SHA-256 checksums.
Keep generated release ZIPs, sample outputs, and reports outside `replication/`, for example under `release_outputs/`.
Do not package the entire repository, the nested Git dependency, original notebooks, credentials, or the bulk data tree.
Verify the GitHub commit before supplying the matching ZIP to the existing Zenodo draft.

Validation performed on 5 October 2026:

- Five offline checks passed for historical and complete-month leap-year bounds, fractional humidity, linear-power RVI, fire masks, FRP scaling, and the historical minimum alias.
- All command-line help and four core dry-run plans passed without Earth Engine initialization.
- All 297 entries across the two local JAXA tile mappings matched direct tile-ID bounds; the four subtiles from one real JAXA raster also matched its archived mapping exactly.
- Six generated calendar rasters matched the archived dimensions, CRS, transforms, and pixel values after normalizing missing pixels to `-9999`.
- The first 5,000 calendar month rows matched the archived CSV, including blank missing values, with zero numeric tolerance for the month columns.
- One Indonesia administrative distance matched its archived value exactly at `1182.5462921083658` km.
- Fifty archived Indonesia FRP JSON records matched the archived CSV within `1e-12`; this checks archive consistency, not a new satellite extraction.
- The first 1,000 handoff CSV rows passed bounded schema, type, missingness, and duplicate-key checks; the CSV has 50 columns and additional rows were not inspected.

Live Earth Engine validation is currently unavailable because the saved credentials return `invalid_grant`; authenticate again before a real tile-month comparison.
No cloud export or analysis model has been run during preparation.

## Outstanding publication requirements

Confirm the latest Methods and data description, exact historical tile subset, CAMS versus GHAP PM2.5 provenance, and the fire measurements used in reported results.
Recover the Black Marble preprocessing and the exact custom crop mask, including an independent acquisition or rebuild route.
Obtain a small frozen extraction reference sample and compare a live run once credentials and asset access are restored.
Clarify which optional channels are required, and reconcile Level-1C versus Level-2A NDVI and SMAP versus GLDAS descriptions.
Add the team's code license, manuscript identity, verified release identity, and published DOI once agreed.
Merge this extraction description with Eugenia's README and analysis files only after access to her existing Zenodo draft is granted.

## Third-party attribution and license

The two vendored Sentinel-1 modules retain the upstream algorithms, normalize trailing whitespace, and include the full MIT notice in their Python headers.
Their source is [gee_s1_ard](https://github.com/adugnag/gee_s1_ard), revision `b50430bd9b2b00e1392532202b88ded6c416932a`.
Cite [Mullissa et al. (2021), Sentinel-1 SAR Backscatter Analysis Ready Data Preparation in Google Earth Engine](https://doi.org/10.3390/rs13101954) and [Vollrath et al. (2020), Angular-Based Radiometric Slope Correction](https://doi.org/10.3390/rs12111867).
The upstream MIT license applies to that dependency; a license for the team's own code remains to be agreed before public deposit.
Data access and redistribution conditions are separate from software licensing.

```text
MIT License

Copyright (c) 2021 Adugna Mullissa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files, to deal
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
```
