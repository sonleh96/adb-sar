# Satellite extraction preparation release

This code-only package translates the available extraction workflow into Python scripts for NDVI, Sentinel-1 RVI, CAMS PM2.5, ERA5-Land meteorology, Black Marble nighttime lights, fire data, JAXA crop masks, rice calendars, and two legacy fire summaries.
The channel command exports ESI and Aqua FPAR, as confirmed by Eugenia on 6 October 2026.
The archive contains this README, `requirements.txt`, and Python files.

The 6 October 2026 bicubic correction for coarse continuous sources changes values from earlier nearest-neighbor outputs.
This package recovers the historical covariate branch and adapts the original Python nightlights pipeline to local files.
Detection-level fire preparation is a documented reconstruction because the original point-data code remains unrecovered.
There is no Zenodo DOI yet.

Son's contribution ends with the extraction data delivered to Eugenia, including `SAR_SVN_rice_reprod.csv`.
Her later dataset preparation, Stata results, classifications, and figures belong to the analysis replication contribution.
These scripts neither reconstruct those steps nor establish that concatenated exports reproduce the delivered CSV.
The CSV has additional `av_*`, plot, and lag fields whose pre-handoff construction remains unresolved; responsibility must be confirmed rather than assumed.

Contact: Son Le, sonle.h96@gmail.com.
GitHub: [sonleh96/adb-sar](https://github.com/sonleh96/adb-sar).
Historical covariate revision: `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`.
Other notebook translations were initially reviewed at `c2766214c17e47cac94dc441c8e5353f1ee6931f`.
The repository retains the original notebooks as historical sources, but the archive excludes them and the Python workflow does not require them.
Notebook cell numbers below are one-based and include every cell.

## Files and provenance

| Python module | Purpose | Historical source |
| --- | --- | --- |
| `config.py`, `common.py` | Configuration, monthly bounds, tiles, rice masks, sampling, and exports | `process_datasets.ipynb`, cells 13, 15, 29-30 |
| `extract_covariates.py` | Recovered RVI, CAMS, meteorology, NTL, and elevation stack with corrected bicubic upsampling | `process_datasets.ipynb`, cell 120 at `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8` |
| `extract_ndvi.py` | Monthly rice NDVI mean, minimum, and maximum | `process_datasets.ipynb`, cells 24, 29-30 |
| `extract_rvi.py` | RVI, with optional additional SAR summaries | `process_datasets.ipynb`, cells 13, 15, 34-35 |
| `extract_fire.py` | Administrative MODIS FRP statistics or separate FIRMS T21 statistics | `docs/analysis/frp.ipynb`, cells 13-14; `process_datasets.ipynb`, cell 20 |
| `extract_channels.py` | ESI and Aqua-selected FPAR statistics | `extract_channels.ipynb`, cell 5, restricted to the confirmed paper channels |
| `prepare_inputs.py` | JAXA raster metadata to subtile bounds | `split_jaxa_tiles.ipynb` |
| `prepare_crop_mask.py` | Categorical JAXA Vietnam 2020 v23.09 mosaic | Author-confirmed source; original notebook uploads `LULC_VN` and selects `b1 == 3` |
| `prepare_nightlights.py` | Local Black Marble cleaning, temporal gap filling, and monthly mosaics | Author-confirmed Python pipeline in `wb_nightlights_production`, revision `44f0c80ce8ecd89a4cea33f85efe7886c55faae1` |
| `prepare_fire_detections.py` | FIRMS MODIS CSVs to point measurements and GADM admin-1 lookup | New reconstruction from the manuscript's data description and official FIRMS fields |
| `prepare_fire_distances.py` | Administrative centroid distance to the selected southern Vietnam tile union | `docs/analysis/frp.ipynb`, cells 5-11 |
| `prepare_calendar.py` | Historical rice harvest calendar raster conversion and coordinate sampling | `extract_channels.ipynb`, cells 30-31, 42-48 |
| `assemble_outputs.py` | Streaming CSV concatenation and flat fire JSON-to-CSV conversion | Portable helper; fire conversion follows the concatenation in `docs/analysis/frp.ipynb`, cell 17 |
| `validate_sample.py` | Offline method checks, bounded CSV inspection, and supplied-sample comparison | New validation helper |
| `validate_channel_graph.py` | Optional offline check of the actual Earth Engine channel graph and QC expression | New validation helper using SDK algorithm metadata |
| `validate_resampling.py` | Checks source-image bicubic ordering and the recovered covariate stack | Production Earth Engine graph inspection |
| `validate_crop_mask.py`, `validate_nightlights.py`, `validate_fire_detections.py` | Small real-file command-line checks | New validation helpers |
| `build_release.py` | Deterministic code-only ZIP and checksum inventory | New packaging helper |
| `vendor/gee_s1_ard/*.py` | Historical Sentinel-1 filtering and terrain correction | Upstream revision `b50430bd9b2b00e1392532202b88ded6c416932a` |

Optional SAR summaries combine a later wheat branch with the selected rice mask, so they do not establish the source of the rice handoff's `vv`, `vh`, and `vvvh` columns.
CSV concatenation preserves text values instead of the notebook's `float16` casting.

## Environment

Use Python 3.11 with `requirements.txt`.
Help, dry runs, CSV assembly, basic checks, and packaging use the standard library.
Earth Engine execution needs `earthengine-api`; JAXA and calendar tools need `rasterio`, `numpy`, `xarray`, and a NetCDF backend such as `scipy`; fire distances need `shapely` and `pyproj`; detection preparation needs `shapely` and optional `pandas`; nightlights need `h5py`, `numpy`, and `rasterio`.

Checks used Python 3.11.11, `earthengine-api==0.1.401`, `numpy==1.26.4`, `xarray==2023.6.0`, `scipy==1.11.4`, `rasterio==1.4.3`, `affine==2.4.0`, `shapely==2.0.6`, `pyproj==3.6.1`, `pandas==2.1.4`, and `h5py==3.9.0`.
Keep `affine==2.4.0` because 3.0.1 failed on a real JAXA transform under Python 3.11.
Neither `geemap` nor Jupyter is required.

From the GitHub repository root, install the supported execution dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

The root requirements file delegates to `replication/requirements.txt`; from an unzipped archive, install that file from the directory containing `replication/`.
On Linux or macOS, use `python3.11 -m venv .venv` and `.venv/bin/python`.
Activate the environment or replace `python` in later commands with its executable.
Direct dependencies are pinned, but transitive dependencies are not locked.

Keep credentials outside the code directory.
Run `earthengine authenticate` separately, choose a registered Google Cloud project, and verify access to every custom asset.
The scripts never open a login flow; historical asset names grant no access.
See the official [Earth Engine authentication guide](https://developers.google.com/earth-engine/guides/auth).

## Required inputs

1. Select the exact historical tiles or derive JSON bounds from the original JAXA rasters.
   `shapefiles/JAXA_subtiles.json` and `JAXA_subtiles_full.json` map tile IDs to `[west, south, east, north]` in EPSG:4326, but the paper subset needs confirmation.
   `--tile-id N10E105_0_1` uses nominal half-degree bounds; use raster-derived bounds when precision matters.
2. Supply an Earth Engine crop-mask image with band `b1` and rice class `3`.
   The historical default is `projects/ee-sonle96/assets/LULC_VN`.
   Son confirmed the source as the [JAXA Vietnam 2020 map, version v23.09](https://www.eorc.jaxa.jp/ALOS/en/dataset/lulc/lulc_vnm_v2309_e.htm), mosaicked from its 10 m tiles.
   Register with JAXA, run `prepare_crop_mask.py` on the original tiles, and upload the categorical GeoTIFF with band `b1` and mode pyramiding.
3. Supply preprocessed monthly nighttime-light images named `VNM_bm_YYYY_MM`, each with band `b1`.
   The historical prefix is `projects/ee-sonle96/assets/BM_VN_processed`.
   Run `prepare_nightlights.py` on monthly VNP46A3 HDF5 granules and annual EOG lit masks, then upload each monthly GeoTIFF with band `b1`.
4. For fire statistics, supply the relevant administrative polygons, their identifier column, and administrative level.
   The later notebook uses level 1 for Thailand and Indonesia and level 2 for other countries.
   The original FIRMS country geometry is the union of `FAO/GAUL/2015/level2` polygons filtered to Indonesia, rather than the GADM boundaries used by the later FRP branch.
   A comparable FIRMS run must reproduce that geometry because other boundaries change the spatial statistics.
   `prepare_fire_distances.py` projects both the selected tile union and administrative polygons to EPSG:3405, computes their centroids, and measures Euclidean distances in kilometers.
   It returns the EPSG:4326 administrative geometries with a distance property, whereas the notebook returned projected centroids.
   Distances alone do not reconstruct fitted instruments, so supply the exact tiles and regional filters.
5. For calendar processing, supply the original `1_Transplanting_Harvest_Group.nc` and `3_Transplanting_Harvest_Cropping.nc`, and a coordinate CSV with `lon` and `lat`.
   The archive excludes all rasters, NetCDF files, boundaries, reference CSVs, and generated outputs.

## Extraction definitions and handoff fields

This candidate mapping comes from visible source names and the delivered CSV header.
Confirm it against the manuscript and historical assembly code before claiming complete provenance.

| Extraction field | Candidate handoff field | Definition and units |
| --- | --- | --- |
| `NDVI_mean` | `ndvi` | Monthly mean of `(B8-B4)/(B8+B4)` from Sentinel-2 Harmonized Level-1C; unitless |
| `RVI_mean` | `rvi` | Monthly mean of `4*VH/(VV+VH)` using linear Sentinel-1 power; unitless |
| `PM25_mean`, `PM25_max` | `pm25_mean`, `pm25_max` | CAMS NRT surface PM2.5 mean/max multiplied by `1e9`; micrograms per cubic meter |
| `Temperature_mean`, `Temperature_max` | `temp_av`, `temp_max` | Mean/max of ERA5-Land daily `temperature_2m`, minus 273.15; degrees Celsius |
| `Rel_humidity_mean` | `hum_av` | Magnus expression evaluated after separately averaging temperature and dew point; fraction, not percent |
| `Precipitation_sum` | `rain_cum` | Sum of ERA5-Land daily `total_precipitation_sum`; meters |
| `Luminosity` | `luminosity` | Cleaned and gap-filled VNP46A3 snow-free radiance, scaled by 0.1; nW/cm2/sr |
| `ESI_4wk_mean` | `esi_4wk_mean` | Climate Engine four-week ESI monthly mean |
| `FPAR_Aqua_mean` | `fpar_aqua_mean`, then analysis `fpar` | MODIS FPAR, scaled by 0.01, with the historical QC and Aqua sensor-bit masks; the downstream rename needs documentation |
| `MaxFRP_*_*` | Legacy regional output | Temporal mean/max or historical minimum alias, followed by spatial mean/max/min; MW; not the paper's detection table |
| `Mean_T21`, `Max_T21` | Legacy country output | Separate FIRMS T21 brightness-temperature series; kelvin; not the paper's detection table |

Relative humidity uses `exp((Td-T)*243.04*17.625 / ((T+243.04)*(Td+243.04)))` with monthly mean `T` and `Td` in degrees Celsius, not daily relative humidity averaged over a month.
The maximum temperature field aggregates the daily mean temperature band, not the separate ERA5 daily maximum band.

NDVI uses `COPERNICUS/S2_HARMONIZED`, which the official catalog identifies as [Level-1C top-of-atmosphere reflectance](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_HARMONIZED).
The historical rice branch adds no cloud-quality mask and is preserved here.
RVI uses Sentinel-1A descending IW scenes with both VV and VH, the actual mono-temporal Lee Sigma filter with kernel 3, and VOLUME terrain flattening using SRTM with zero additional buffer.
Unused multi-temporal labels do not describe the executed filter.
The channel script exports only ESI and Aqua FPAR, each with monthly mean, minimum, and maximum.
It removes Terra FPAR, soil moisture, and ET before sampling, so their missing values cannot drop valid ESI/Aqua rows.
A fresh export may therefore contain coordinates absent from the old 15-band stack.
The historical `sm_root_mean` and `fpar_terra_mean` handoff columns are outside this revised extraction scope.

Aqua FPAR uses the original `MODIS/061/MCD15A3H` four-day product, `FparLai_QC` bit 1 equal to 1, SCF_QC bits 5-7 not equal to 4, and scale factor 0.01.
It is the Aqua-selected combined-product field, not MYD15.
See the [MCD15A3H product and QC definitions](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD15A3H).

The default sampling is EPSG:4326 at a nominal 100 m, with the 10 m class-3 rice mask.
CAMS, ERA5, Black Marble, ESI, and Aqua FPAR use bicubic resampling before monthly reducers and crop masking.
FPAR flags are evaluated on the native grid first.
JAXA classes and flags stay nearest-neighbor, and NDVI/RVI handling is unchanged.
Interpolation before monthly extrema differs from interpolation afterward, and bicubic can overshoot because no range clipping is applied.
This method does not reproduce earlier nearest-neighbor values.
See the [Earth Engine resampling guide](https://developers.google.com/earth-engine/guides/resample).
The 100 m output grid adds no native detail to coarse inputs, and sampling drops any pixel with a null band.
The recovered combined stack contains nine bands: RVI, PM2.5 mean/max, temperature mean/max, relative humidity, precipitation, luminosity, and elevation.
In `process_datasets.ipynb` at `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`, cell 117 requests January-December 2017 and cell 120 excludes the commented Sentinel-5P and wind calculations.
The branch also exists at `2e6585c2ee95fa927e1e0c3f6a35c5413af8eaf7`; revision `40f5524` later reactivated those bands during annotation, but this translation follows the earlier branch.
Standalone NDVI, RVI, and channel exports have their own joint validity masks and may have different coordinate sets.

Earth Engine date ends are [exclusive](https://developers.google.com/earth-engine/apidocs/ee-imagecollection-filterdate).
The default `--date-mode historical` omits the last day by passing it as the exclusive end; `--date-mode full-month` uses the next month's first day and changes the data.
Do not substitute corrected date bounds for historical outputs without a real comparison and agreement with the manuscript authors.

Historical mode assigns temporal `MaxFRP_min` with `.max()`; corrected mode uses `.min()` and changes results.
FRP is scaled by 0.1 as specified for [MOD14A1 MaxFRP](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD14A1).
The source quality rule retains FireMask low bits at least 7 and QA land/water low bits at most 2.
FIRMS T21 and MODIS FRP are different fire measurements.
The current paper uses detection-level FRP and brightness temperatures for channels 21/22 and 31, supplied to Stata as `FRP_son.dta` with the `lon-lat-adm1.csv` lookup.
`prepare_fire_detections.py` reconstructs those points and administrative assignments from standard FIRMS MODIS CSVs; legacy summaries remain separate.

## Local source preparation

### JAXA rice-area mosaic

`prepare_crop_mask.py` mosaics the original Vietnam 2020 v23.09 categorical tiles without binary conversion; extraction selects class 3 from uploaded `LULC_VN`.
Retain the tiles and download metadata.
Use `python -m replication.prepare_crop_mask --help` for the input directory and output arguments.

```powershell
python -m replication.prepare_crop_mask --input-dir inputs/Vietnam_v23.09_10m --output release_outputs/LULC_VN.tif
python -m replication.prepare_crop_mask --input-dir inputs/Vietnam_v23.09_10m --output release_outputs/LULC_VN.tif --write
```

The first command plans the mosaic; the second writes it in bounded chunks.
The 60 tiles form an 89,064 by 178,128 union over 102-110 E and 8-24 N.
The tiled, compressed BigTIFF preserves classes 1-12, uses zero as gap nodata, and rejects overlap or misalignment; the plan reports uncompressed and buffer sizes.

### Black Marble nighttime lights

Son confirmed the monthly-input pipeline at [wb_nightlights_production](https://github.com/sonleh96/wb_nightlights_production/tree/44f0c80ce8ecd89a4cea33f85efe7886c55faae1).
This adaptation follows `src/utils/utils_process.py`, `src/utils/utils_impute.py`, and their drivers, removes cloud/demo constraints, and retains the Python numerical rules.
The repository's Vietnam R scripts use different filters and endpoint interpolation.

Obtain monthly VNP46A3 Collection 001 HDF5 granules from [NASA LAADS](https://ladsweb.modaps.eosdis.nasa.gov/) and annual lit masks from [EOG's VNL products](https://eogdata.mines.edu/products/vnl/).
The original `data/LAADS_query_processed.csv` manifest confirms Collection 001, whose names and versions must be retained.
For the requested 2017-2022 outputs, include December 2016 and an explicit EOG mask for every input year, including 2016.
Vietnam uses tiles `h28v06`, `h28v07`, `h28v08`, and `h29v07`.
Provide complete months for each selected tile-year plus preceding December; incomplete inputs and EOG masks that do not cover every selected pixel are rejected.

```powershell
python -m replication.prepare_nightlights --input-dir inputs/VNP46A3 --output-dir release_outputs/nightlights_2017 --year 2017 --mask 2016=inputs/eog/2016_mask.tif --mask 2017=inputs/eog/2017_mask.tif
```

Repeat `--year` and `--mask` for more years.
`--output-dir` must be new; by default all discovered tiles are used, while repeated `--tile h28v08` arguments select a subset.
`--reuse-mask TARGET_YEAR=SOURCE_YEAR` records deliberate annual-mask reuse in the manifest.
Each `VNM_bm_YYYY_MM.tif` is a single-band float32 mosaic on the source grid, without country-polygon clipping.

The retained cleaning and gap-filling rules are:

1. Read `AllAngle_Composite_Snow_Free`, its quality layer, and `Land_Water_Mask`.
2. Set negative raw radiance to zero; mark raw values at least 65535, quality flag 1, and land/water values above 150 as missing.
3. Multiply radiance by 0.1 and set pixels where the nearest-neighbor EOG lit mask is zero to zero.
4. For each year, concatenate the preceding cleaned December and January-December, interpolate along equally spaced month indices with linear extrapolation, and export the requested months.
5. At final export, set negative interpolated values and unresolved missing values to zero, matching the source's `where(value >= 0, 0)` behavior.

This Python workflow has no 10000 cutoff, spatial smoothing, or R 8-bit conversion.
The [NASA Black Marble guide](https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/archives/Document%20Archive/Science%20Data%20Product%20Documentation/VIIRS_Black_Marble_UG_v1.3_Sep_2022.pdf) documents radiance in nW/cm2/sr.
The recovered driver shifts month labels by dropping December while reading from index zero.
This adaptation makes `VNM_bm_YYYY_01.tif` contain January, so historical files may differ and byte identity is not claimed.
Use `python -m replication.prepare_nightlights --help` for the explicit local input and output arguments.

### Detection-level fire inputs

Download standard science-quality MODIS Collection 6.1 Terra and Aqua CSVs for the desired dates and regions from the [FIRMS archive](https://firms.modaps.eosdis.nasa.gov/download/).
Use [GADM 4.1](https://gadm.org/download_world.html) admin-1 GeoJSON boundaries for the same regions.
The script rejects near-real-time records, VIIRS observations, and other collections.
The [FIRMS archive README](https://firms.modaps.eosdis.nasa.gov/download/Readme.txt) explains the archive naming and standard versus near-real-time distinction.

```powershell
python -m replication.prepare_fire_detections --inputs "inputs/fire_archive_M-C61_*.csv" --gadm "inputs/gadm41_*_1.json" --output-dir release_outputs/fire_detections --repair-invalid-geometries --write-dta
```

The default inclusive period is 2017-01-01 through 2022-12-31.
Default country selection is China, Laos, Thailand, Myanmar, Cambodia, Indonesia, and Malaysia.
Use `--admin1-ids` to specify the intended southern China provinces or other regional subset explicitly; no undocumented historical subset is assumed.
All confidence levels remain; no seasonal, distance, or hotspot-type filter is applied.
FRP remains in MW, `brightness` and `bright_t31` remain in kelvin, and `T31` is an alias of `bright_t31`.
Original FIRMS fields remain, with `lat`, `lon`, `year`, `mon`, `T31`, `country`, and `gid_1` added.
Acquisition time is retained as a four-character UTC HHMM string.
Myanmar's country label defaults to the legacy `MYM`; GADM identifiers retain `MMR`.

Outputs are `FRP_son.csv`, optional `FRP_son.dta`, `lon-lat-adm1.csv`, and `fire_manifest.json`.
The manifest records source and output checksums, selection rules, counts, and geometry repairs.
Covering polygons assign regions; duplicate, unmatched, or multiply assigned points fail unless explicit policy flags allow them.
The example opts into geometry repair because two local Indonesian admin-1 geometries are invalid; repaired IDs are recorded.
CSV preparation uses a disk index; optional Stata export loads the retained table into memory.
Confirm field names, province selections, and any additional historical filtering against Eugenia's actual `FRP_son.dta` and do-file before replacing her inputs.
This reconstruction does not perform the downstream fire-to-PM-grid distance weighting or instrument estimation.

## Execution

Run modules from the directory containing `replication/`, including an unzipped archive's top level.

Start with one tile and one month, using a dry run:

```powershell
python -m replication.extract_ndvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_rvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_channels --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

Dry runs print products, dates, settings, and task count without importing Earth Engine or starting exports.
Use `--tiles-json PATH --tile-id ID` to select a historical tile from an external mapping; repeat `--tile-id` for additional tiles.
Omitting `--tile-id` when supplying a mapping selects every tile in that mapping.
There are no hidden positional tile slices, resume offsets, or one-month demonstration loops.

When the plan and inputs have been checked, add `--project YOUR_PROJECT --crop-mask-asset YOUR_ASSET --submit`.
For covariates, also pass `--ntl-asset-prefix YOUR_MONTHLY_ASSET_FOLDER` if using a different NTL folder.
Submission starts one Drive CSV task per tile-month; verify completion in Earth Engine before download and assembly.
A submission message confirms only task start.
Use a distinct Drive folder for each workflow or historical/corrected run.

Run `python -m replication.extract_fire --help`, `python -m replication.prepare_inputs --help`, `python -m replication.prepare_fire_distances --help`, and `python -m replication.prepare_calendar --help` for the required local input arguments.
The fire command uses explicit regional inputs and writes regional monthly statistics separately from rice-grid exports.
Calendar conversion uses 2019 and defaults to the historical center-as-outer-bounds transform.
`--mode corrected` infers cell edges and may sample a different cell.
Historical files have ascending longitude and descending latitude, so rows need no flip.
CSVs use blank missing values; GeoTIFFs use `-9999`.
By default, dates output contains month numbers under `*_doy`; `--sampling-mode corrected` writes actual day-of-year values while keeping converted months in the month file.
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

The fire example is an offline plan; add `--project YOUR_PROJECT --submit` to request regional values.
Use a small coordinates-only CSV for calendar sampling, rather than the complete multi-gigabyte handoff file.
CSV assembly requires identical ordered headers and retains text values.
Fire JSON conversion uses a stable union header, writes JSON null as blank, and adds no numeric precision reduction.
Keep MODIS FRP and FIRMS T21 inputs separate; T21 JSON conversion uses `--key Timestamp --key country` instead of `GID` and `date`.
The default duplicate check covers only the first 100,000 rows; `--duplicate-check sqlite` checks all exact text keys on disk.

## Validation and archive preparation

```powershell
python -m replication.validate_sample --self-test
python -m replication.validate_sample --channel-graph-check --report release_outputs/channels_graph_validation.json
python -m replication.validate_resampling
python -m replication.validate_crop_mask --real-raster inputs/Vietnam_v23.09_10m/N08E104_2020_v23.09_10m.tif
python -m replication.validate_nightlights
python -m replication.validate_fire_detections
python -m replication.validate_sample --csv PATH_TO_HANDOFF.csv --rows 1000
python -m replication.validate_sample --reference historical_sample.csv --candidate new_sample.csv --key Timestamp --key lon --key lat --tolerance NDVI_mean=0.00001 --rows 1000
python -m replication.validate_sample --frp-json-dir HISTORICAL_IDN_JSON_DIRECTORY --frp-csv HISTORICAL_IDN_FRP.csv --rows 50
python -m replication.build_release --output release_outputs/adb-sar-extraction-preparation.zip
```

Large-CSV validation is bounded.
The optional channel graph check uses the installed Earth Engine SDK and bundled metadata to build the graph offline, check sources and bands, and test all 256 QC bytes.
It does not authenticate, access custom assets, or compare remote pixels.
Use an independently supplied historical sample for value comparisons and explicit keys and tolerances appropriate to the source precision.
Prefix inspection does not establish full coverage or field provenance.
The delivered CSV contains rounded values, and the exploratory assembly code used reduced precision; exact decimal equality may therefore be inappropriate for comparisons with fresh exports.

The release builder packages Python files, this README, and `requirements.txt`, verifies the ZIP, and records SHA-256 checksums.
Keep generated release ZIPs, sample outputs, and reports outside `replication/`, for example under `release_outputs/`.
Do not package the entire repository, the nested Git dependency, original notebooks, credentials, or the bulk data tree.
Verify the GitHub commit before supplying the matching ZIP to the existing Zenodo draft.

Validation on 5 October 2026:

- Five offline checks passed for historical and complete-month leap-year bounds, fractional humidity, linear-power RVI, fire masks, FRP scaling, and the historical minimum alias.
- All command-line help and four core dry-run plans passed without Earth Engine initialization.
- All 297 entries across the two local JAXA tile mappings matched direct tile-ID bounds; the four subtiles from one real JAXA raster also matched its archived mapping exactly.
- Six generated calendar rasters matched the archived dimensions, CRS, transforms, and pixel values after normalizing missing pixels to `-9999`.
- The first 5,000 calendar month rows matched the archived CSV, including blank missing values, with zero numeric tolerance for the month columns.
- One Indonesia administrative distance matched its archived value exactly at `1182.5462921083658` km.
- Fifty archived Indonesia FRP JSON records matched the archived CSV within `1e-12`; this checks archive consistency, not a new satellite extraction.
- The first 1,000 handoff CSV rows passed bounded schema, type, missingness, and duplicate-key checks; the CSV has 50 columns and additional rows were not inspected.

Seven method tests and channel graph validation passed on 6 October 2026.
The graph contains only ESI and MCD15A3H sources and six ESI/Aqua bands; all 256 QC bytes matched the Aqua rule, with 112 accepted.
Resampling checks covered five production graphs and the nine-band covariate stack.
Real CLI fixtures covered HDF5, GeoTIFF, CSV, GeoJSON, and optional Stata output.
Six fire tests covered Stata time preservation and duplicate, invalid, unassigned, and ambiguous records.
Five nightlights tests covered 24 outputs from 50 granules, month labels, cleaning, mask alignment, and incomplete inputs.
Interpolation also matched the source xarray method for 15,600 seeded values, including sparse and empty series.
JAXA checks covered the 60-tile layout, one exact 64 by 64 source window, adjacent classes, overlap rejection, and input-overwrite refusal.
These checks establish tested behavior and archive contents, not the paper's estimates.

## Outstanding publication requirements

The manuscript identifies CAMS PM2.5 and MODIS detection-level fire metrics.
Before publication, confirm the historical tiles, pre-handoff joins, derived fields, fire schema, regions, and filters; retain Black Marble inputs with versions and checksums; document bicubic and nightlights methods; and add the code license, manuscript identity, release identity, and DOI.
The combined deposit guide is `zenodo/README.md`; Eugenia can upload it with both contributions without granting Son draft access.

## Third-party attribution and license

The two vendored Sentinel-1 modules retain the upstream algorithms, normalize trailing whitespace, and include the full MIT notice in their Python headers.
Their source is [gee_s1_ard](https://github.com/adugnag/gee_s1_ard), revision `b50430bd9b2b00e1392532202b88ded6c416932a`.
Cite [Mullissa et al. (2021), Sentinel-1 SAR Backscatter Analysis Ready Data Preparation in Google Earth Engine](https://doi.org/10.3390/rs13101954) and [Vollrath et al. (2020), Angular-Based Radiometric Slope Correction](https://doi.org/10.3390/rs12111867).
The upstream MIT license applies to that dependency; a license for the team's own code remains to be agreed before public deposit.
Data access and redistribution conditions are separate from software licensing.

The adapted nightlights implementation is derived from [sonleh96/wb_nightlights_production](https://github.com/sonleh96/wb_nightlights_production), revision `44f0c80ce8ecd89a4cea33f85efe7886c55faae1`.
Its MIT licence, copyright 2022 sonleh96, is retained in `prepare_nightlights.py`.

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
