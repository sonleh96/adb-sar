# Satellite extraction preparation release

This package translates the available satellite and environmental extraction code into ordinary Python scripts.
It covers NDVI, Sentinel-1 RVI, CAMS PM2.5, ERA5-Land temperature and humidity, Black Marble nighttime-light preprocessing, and MODIS detection-level fire preparation.
The channel module covers ESI and Aqua FPAR only, as confirmed by Eugenia on 6 October 2026.
Other helpers mosaic JAXA crop-map tiles, prepare extraction tile definitions, sample rice calendars, and retain two legacy fire-summary workflows.
The code archive contains this README and Python files only.

The author requested bicubic resampling for coarse continuous sources on 6 October 2026.
That correction changes values relative to earlier nearest-neighbor outputs.
The historical covariate branch has been recovered, and the original Python nightlights pipeline has been identified and adapted for local files.
Detection-level fire preparation is a documented reconstruction; the lost original point-data code has not been found.
There is no Zenodo DOI for this package yet.

Son's contribution ends at the extraction data delivered to Eugenia, including `SAR_SVN_rice_reprod.csv`.
Eugenia's later preparation of analysis or training datasets, Stata results, crop and drought classifications, and figures belongs to her analysis replication contribution.
These scripts do not reconstruct those later steps or assert that concatenating exports recreates the delivered CSV.
The delivered CSV already contains additional derived fields, including `av_*`, plot identifiers, and lags; their pre-handoff construction is not established by the extraction scripts reviewed here.
Responsibility for any missing pre-handoff transformations must be confirmed rather than automatically assigned to Eugenia.

Contact: Son Le, sonle.h96@gmail.com.
GitHub: [sonleh96/adb-sar](https://github.com/sonleh96/adb-sar).
Historical covariate revision: `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`.
Other notebook translations were initially reviewed at `c2766214c17e47cac94dc441c8e5353f1ee6931f`.
The original notebooks are retained in the repository as historical source material and are not required by the Python workflow or included in this archive.
Cell references below count all notebook cells, starting at one.

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

The optional SAR summaries use statistics from a later wheat branch with the rice mask explicitly selected here.
Their inclusion does not establish that the same branch generated the rice handoff's `vv`, `vh`, and `vvvh` columns.
The new concatenation helper preserves CSV text values rather than reproducing the exploratory notebook's `float16` casting.

## Environment

Use Python 3.11 or newer.
Command-line help, extraction dry runs, CSV assembly, basic method checks, and packaging use the standard library.
The raster, detection, and Earth Engine graph validators also require their corresponding execution dependencies.
Earth Engine execution additionally needs `earthengine-api`.
JAXA raster preparation and calendar processing additionally need `rasterio`, `numpy`, `xarray`, and a NetCDF backend such as `scipy`.
Fire-distance preparation additionally needs `shapely` and `pyproj`.
Detection-level fire preparation needs `shapely`, with `pandas` for optional Stata output.
Nightlights preparation needs `h5py`, `numpy`, and `rasterio`.

The local checks used Python 3.11.11, `earthengine-api==0.1.401`, `numpy==1.26.4`, `xarray==2023.6.0`, `scipy==1.11.4`, `rasterio==1.4.3`, and `affine==2.4.0`.
The fire-distance comparison used `shapely==2.0.6` and `pyproj==3.6.1`; local fire and nightlights tests used `pandas==2.1.4` and `h5py==3.9.0`.
Pin `affine==2.4.0` with this environment: version 3.0.1 failed while reading a real JAXA raster's transform under Python 3.11.
Those versions document the checked environment.
Neither `geemap` nor Jupyter is required.

From a fresh environment, install the optional execution dependencies as needed:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install earthengine-api==0.1.401 numpy==1.26.4 xarray==2023.6.0 scipy==1.11.4 rasterio==1.4.3 affine==2.4.0 shapely==2.0.6 pyproj==3.6.1 pandas==2.1.4 h5py==3.9.0
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
   Use raster-derived bounds when exact coordinates matter.
2. Supply an Earth Engine crop-mask image with band `b1` and rice class `3`.
   The historical default is `projects/ee-sonle96/assets/LULC_VN`.
   Son confirmed the source as the [JAXA Vietnam 2020 map, version v23.09](https://www.eorc.jaxa.jp/ALOS/en/dataset/lulc/lulc_vnm_v2309_e.htm), mosaicked from its 10 m tiles.
   Obtain the original tiles through JAXA's registration process, run `prepare_crop_mask.py`, and upload the single-band categorical GeoTIFF to your Earth Engine assets.
   Preserve categorical values during upload, use a mode pyramiding policy, and retain band name `b1`.
3. Supply preprocessed monthly nighttime-light images named `VNM_bm_YYYY_MM`, each with band `b1`.
   The historical prefix is `projects/ee-sonle96/assets/BM_VN_processed`.
   Run `prepare_nightlights.py` using monthly VNP46A3 HDF5 granules and annual EOG lit masks, following the recovered Python pipeline described below.
   Upload each output GeoTIFF as the corresponding monthly asset, with band `b1`.
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
| `Luminosity` | `luminosity` | Cleaned and gap-filled VNP46A3 snow-free radiance, scaled by 0.1; nW/cm2/sr |
| `ESI_4wk_mean` | `esi_4wk_mean` | Climate Engine four-week ESI monthly mean |
| `FPAR_Aqua_mean` | `fpar_aqua_mean`, then analysis `fpar` | MODIS FPAR, scaled by 0.01, with the historical QC and Aqua sensor-bit masks; the downstream rename needs documentation |
| `MaxFRP_*_*` | Legacy regional output | Temporal mean/max or historical minimum alias, followed by spatial mean/max/min; MW; not the paper's detection table |
| `Mean_T21`, `Max_T21` | Legacy country output | Separate FIRMS T21 brightness-temperature series; kelvin; not the paper's detection table |

Relative humidity uses `exp((Td-T)*243.04*17.625 / ((T+243.04)*(Td+243.04)))` with monthly mean `T` and `Td` in degrees Celsius.
This is not the mean of daily relative humidity.
The maximum temperature field aggregates the daily mean temperature band, not the separate ERA5 daily maximum band.

NDVI uses `COPERNICUS/S2_HARMONIZED`, which the official catalog identifies as [Level-1C top-of-atmosphere reflectance](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_HARMONIZED).
The historical rice branch adds no cloud-quality mask and is preserved here.
RVI uses Sentinel-1A descending IW scenes with both VV and VH, the actual mono-temporal Lee Sigma filter with kernel 3, and VOLUME terrain flattening using SRTM with zero additional buffer.
The notebook's unused multi-temporal configuration labels are not used to describe that executed filter.
The channel script exports only ESI and Aqua FPAR, each with monthly mean, minimum, and maximum.
It excludes Terra FPAR, soil moisture, and the unused ET product before sampling, rather than merely hiding their CSV columns.
Those removed bands can no longer discard otherwise valid ESI/Aqua observations through a joint missing-value mask.
A fresh export can therefore include coordinates missing from the old 15-band channel stack; equality of sample coverage is not established.
The historical `sm_root_mean` and `fpar_terra_mean` handoff columns are outside this revised extraction scope.

Aqua FPAR retains the original `MODIS/061/MCD15A3H` combined four-day product and selects pixels with `FparLai_QC` bit 1 equal to 1.
SCF_QC bits 5-7 must differ from 4, and the `Fpar` scale factor is 0.01.
This is the Aqua-selected field from the combined product, not the separate MYD15 Aqua product.
See the [MCD15A3H product and QC definitions](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD15A3H).

The default sampling is EPSG:4326 at a nominal 100 m, with the 10 m class-3 rice mask.
CAMS, ERA5, Black Marble, ESI, and Aqua FPAR continuous source bands now use bicubic resampling before monthly reducers and crop masking, as requested by Son.
FPAR quality and sensor flags are evaluated on the native grid before interpolation.
JAXA classes and quality flags retain nearest-neighbor handling; the original fine-resolution NDVI/RVI handling remains unchanged.
Applying interpolation before monthly extrema differs from interpolating the extrema afterward.
Bicubic can overshoot source ranges; this update adds no physical-range clipping.
This corrects the extraction method rather than reproducing the earlier nearest-neighbor values.
See the [Earth Engine resampling guide](https://developers.google.com/earth-engine/guides/resample).
This output grid does not imply that CAMS, ERA5, NTL, or other coarse input products have native 100 m information.
Sampling drops pixels with a null value in any sampled band.
The recovered combined stack contains nine bands: RVI, PM2.5 mean/max, temperature mean/max, relative humidity, precipitation, luminosity, and elevation.
In `process_datasets.ipynb` at `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`, cell 117 requests January-December 2017 and cell 120 excludes the commented Sentinel-5P and wind calculations.
The same branch exists at `2e6585c2ee95fa927e1e0c3f6a35c5413af8eaf7`.
Revision `40f5524` later reactivated those bands during an annotation rewrite; the Python translation now follows the earlier branch.
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
The current paper uses detection-level FRP and brightness temperatures for channels 21/22 and 31, supplied to Stata as `FRP_son.dta` with the `lon-lat-adm1.csv` lookup.
`prepare_fire_detections.py` reconstructs those point-level measurements and administrative assignments from standard FIRMS MODIS CSVs.
The legacy regional and country summaries remain separate from the point inputs.

## Local source preparation

### JAXA rice-area mosaic

`prepare_crop_mask.py` mosaics the original Vietnam 2020 v23.09 categorical tiles without converting them to a binary rice mask.
The source notebooks upload the map as `LULC_VN` and select class 3 during extraction.
Retain the original tile collection and its download metadata with the data contribution.
Use `python -m replication.prepare_crop_mask --help` for the input directory and output arguments.

```powershell
python -m replication.prepare_crop_mask --input-dir inputs/Vietnam_v23.09_10m --output release_outputs/LULC_VN.tif
python -m replication.prepare_crop_mask --input-dir inputs/Vietnam_v23.09_10m --output release_outputs/LULC_VN.tif --write
```

The first command inspects metadata and prints the mosaic plan; the second writes the mosaic in bounded chunks.
The 60 local tiles form an 89,064 by 178,128 pixel union over 102-110 E and 8-24 N.
The writer preserves classes 1-12, uses zero as nodata for gaps, and rejects overlapping or misaligned tiles.
It writes a tiled, compressed BigTIFF; the plan reports the uncompressed size and working-buffer size before writing.

### Black Marble nighttime lights

Son confirmed that the Python pipeline in [wb_nightlights_production](https://github.com/sonleh96/wb_nightlights_production/tree/44f0c80ce8ecd89a4cea33f85efe7886c55faae1) produced the monthly nightlights inputs.
The local adaptation follows `src/utils/utils_process.py`, `src/utils/utils_impute.py`, and their drivers at that revision.
It removes cloud-bucket configuration and demonstration restrictions while retaining the Python numerical rules.
The Vietnam R scripts in the same repository use different filters and endpoint interpolation and are not the selected method.

Obtain monthly VNP46A3 Collection 001 HDF5 granules from [NASA LAADS](https://ladsweb.modaps.eosdis.nasa.gov/) and annual lit masks from [EOG's VNL products](https://eogdata.mines.edu/products/vnl/).
Collection 001 is confirmed by the original repository's `data/LAADS_query_processed.csv` download manifest.
Retain their original names and product versions; do not silently substitute a newer collection.
For the requested 2017-2022 outputs, include December 2016 and an explicit EOG mask for every input year, including 2016.
Vietnam's source tile list is `h28v06`, `h28v07`, `h28v08`, and `h29v07`; select the tiles covering the requested region.
The script requires complete monthly inputs for each selected tile-year and preceding December.
EOG masks must cover every pixel of the selected HDF5 tiles; a country-cropped mask with missing coverage is rejected.

```powershell
python -m replication.prepare_nightlights --input-dir inputs/VNP46A3 --output-dir release_outputs/nightlights_2017 --year 2017 --mask 2016=inputs/eog/2016_mask.tif --mask 2017=inputs/eog/2017_mask.tif
```

Repeat `--year` and `--mask` for additional years.
Choose a new `--output-dir`; the command refuses to overwrite an existing directory.
The default uses every tile found for the requested years; repeat `--tile h28v08` and other tile IDs to select a subset.
Use `--reuse-mask TARGET_YEAR=SOURCE_YEAR` only when deliberate reuse of a supplied annual mask is appropriate; it is recorded in the manifest.
Each `VNM_bm_YYYY_MM.tif` is a single-band float32 mosaic on the source grid, without country-polygon clipping.

The retained cleaning and gap-filling rules are:

1. Read `AllAngle_Composite_Snow_Free`, its quality layer, and `Land_Water_Mask`.
2. Set negative raw radiance to zero; mark raw values at least 65535, quality flag 1, and land/water values above 150 as missing.
3. Multiply radiance by 0.1 and set pixels where the nearest-neighbor EOG lit mask is zero to zero.
4. For each year, concatenate the preceding cleaned December and January-December, interpolate along equally spaced month indices with linear extrapolation, and export the requested months.
5. At final export, set negative interpolated values and unresolved missing values to zero, matching the source's `where(value >= 0, 0)` behavior.

There is no 10000 raw-value cutoff, spatial smoothing, or optional R 8-bit conversion in this Python workflow.
The [NASA Black Marble guide](https://ladsweb.modaps.eosdis.nasa.gov/api/v2/content/archives/Document%20Archive/Science%20Data%20Product%20Documentation/VIIRS_Black_Marble_UG_v1.3_Sep_2022.pdf) documents radiance in nW/cm2/sr.
The recovered driver drops December from its output filenames but starts reading at time index zero, shifting the exported months.
This adaptation corrects that indexing so `VNM_bm_YYYY_01.tif` contains January; historical files produced by the erroneous driver may therefore differ.
No other claim of byte identity with the old custom assets is made.
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
All confidence levels are retained, and no seasonal, distance, or hotspot-type filter is applied.
FRP remains in MW, `brightness` and `bright_t31` remain in kelvin, and `T31` is an alias of `bright_t31`.
Original FIRMS fields remain, with `lat`, `lon`, `year`, `mon`, `T31`, `country`, and `gid_1` added.
Acquisition time is retained as a four-character UTC HHMM string.
Myanmar's country label defaults to the legacy `MYM`; GADM identifiers retain `MMR`.

Outputs are `FRP_son.csv`, optional `FRP_son.dta`, `lon-lat-adm1.csv`, and `fire_manifest.json`.
The manifest records source checksums, selection rules, counts, geometry repairs, and output checksums.
Point locations are assigned to polygons that cover them.
Duplicate detections, unmatched points, and points covered by multiple regions fail by default; explicit policy flags allow a reviewed alternative.
The example opts into geometry repair because two local Indonesian admin-1 geometries are invalid; repaired IDs are recorded.
CSV preparation streams through a disk index; optional Stata export loads the retained table into memory.
Confirm field names, province selections, and any additional historical filtering against Eugenia's actual `FRP_son.dta` and do-file before replacing her inputs.
This reconstruction does not perform the downstream fire-to-PM-grid distance weighting or instrument estimation.

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

Validation is deliberately bounded for large historical CSVs.
The optional channel graph check requires Earth Engine's installed SDK and its bundled algorithm metadata.
It builds the actual channel image graph offline, checks its source collections and output bands, and evaluates its serialized QC expression for all 256 byte values.
It does not authenticate, access custom assets, or compare remote pixel values.
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

Checks repeated or added on 6 October 2026 include seven offline method tests and the optional channel graph validation.
The graph contains only the ESI and MCD15A3H source collections and six ESI/Aqua output bands.
All 256 QC-byte cases matched the documented Aqua rule, with 112 accepted.
The resampling validator checks five actual production graphs for native source-image bicubic ordering and the recovered nine-band covariate stack.
The local preprocessing validators exercise real command-line programs with small HDF5, GeoTIFF, CSV, GeoJSON, and optional Stata files.
Six fire tests passed, including acquisition-time preservation in Stata and explicit handling of duplicate, invalid, unassigned, and ambiguous records.
Five nightlights tests passed, including a 24-raster output from 50 small HDF5 granules, January/December labels, source cleaning rules, mask alignment, and rejection of incomplete inputs.
Its interpolation also matched the source xarray method for 15,600 seeded values, including sparse and entirely missing pixel series.
JAXA checks cover the complete 60-tile metadata layout, an exact 64 by 64 pixel window from an original raster, adjacent categorical tiles, and refusal of overlaps or accidental input overwrites.
These checks establish the tested behavior and archive contents, not reproduction of the paper's estimates.

## Outstanding publication requirements

The supplied manuscript resolves the main PM2.5 source as CAMS and identifies MODIS detection-level fire metrics.
Confirm the exact historical tile subset and document the remaining pre-handoff joins and derived fields.
Retain the original Black Marble granules and annual EOG masks with their product versions and checksums.
Reconcile the reconstructed fire schema, selected source regions, and any historical filters with the Stata inputs.
Ensure the manuscript describes the corrected bicubic method and the actual nightlights cleaning and interpolation rules.
Add the team's code license, manuscript identity, verified release identity, and published DOI once agreed.
The revised combined deposit README is maintained separately at `zenodo/README.md` in GitHub and supplied to Eugenia for upload with the code archive and her analysis files.
Son does not need editing access to the Zenodo draft for that handoff.

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
