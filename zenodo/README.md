# Replication code: Air pollution and rice crop health: Evidence from Vietnam's Mekong Delta

**Authors:** Eugenia Go, Yohan Iddawela, Son Le, Elaine S. Tan (Asian Development Bank)
**Paper:** [Full citation once published]
**Code DOI:** [Zenodo DOI]
**Extraction-code contact:** Son Le, sonle.h96@gmail.com
**Analysis contact:** [Eugenia to confirm contact details]

This deposit combines recovered Python extraction code with Eugenia's Stata analysis of PM2.5 and rice crop health in Vietnam's Mekong Delta, 2017-2022.
The analysis uses panel fixed effects and instruments based on transboundary fire activity.
Eugenia supplied the Stata descriptions; those files were not run during this extraction update.

---

## 1. Software requirements

Python extraction requires Python 3.11 and the pinned direct dependencies in `replication/requirements.txt`.
Unzip the archive and run `python -m pip install -r replication/requirements.txt` in a virtual environment from the directory containing `replication/`.
See `replication/README.md` for setup and data access.
The archive excludes analysis datasets and Stata files.
Stata requirements follow.

- **Stata** [version, e.g. 18 MP].
  `elasticnet` requires Stata 16 or later.
- **User-written packages** (install each with `ssc install <name>`):

| Package | Used in |
|---|---|
| `reghdfe`, `ftools` | Files 1, 2, 3 |
| `hdfe` | File 1 |
| `boottest` | Files 1, 3 |
| `estout` (includes `esttab`, `estpost`) | Files 1, 3 |
| `carryforward` | File 2 |
| `ivreghdfe`, `ivreg2`, `ranktest` | File 3 |
| [packages used in file 4, if any] | File 4 |

Package versions used: [run `which reghdfe` etc. and list versions here].

---

## 2. How to run

1. Put the Stata do-files and inputs in one folder.
   Unzip the extraction archive there, retaining `replication/`.
   See Section 4 and `replication/README.md` for Python instructions.
2. Open Stata and change to that folder, e.g. `cd "C:/path/to/folder"`.
3. Run the do-files in order:

```stata
do 1_Results-Panel.do
do 2_Results-Fire-ElasticNet-pmgrid.do
do 3_Results-IV.do
do 4_Figures.do
```

Paths are relative to Stata's working folder and need no edits.
Each do-file opens a log.
File 3 uses File 2's output; File 1 runs independently.
[File 4 requires: …]

The wild cluster bootstrap and elastic net cross-validation use fixed seeds (`12345`).

File 1 processes over 10 million plot-month observations; File 2 pairs every fire with every PM2.5 grid cell using `joinby`.
Both require substantial memory.
[Add approximate runtime and memory used.]

---

## 3. Input data

| File | Description | Used in |
|---|---|---|
| `reg_SVN_rice_SpatAuto_with_grid_IDs.dta` | Plot-month panel of rice crop-health indicators, PM2.5, meteorology and night lights | Files 1, 2 |
| `FRP_son.dta` | MODIS active fire detections (fire radiative power, brightness) for Southeast Asia and southern China | File 2 |
| `lon-lat-adm1.csv` | Lookup linking each fire location to its first-level administrative unit (`gid_1`) | File 2 |
| [OWM PM2.5 file for Figure A1] | [Open Weather Maps PM2.5, 22 km, 2022] | File 4 |

Key variables in the panel: `ndvi`, `rvi`, `fpar`, `esi_4wk_mean` (crop-health outcomes); `pm25_mean`; `temp_av`, `hum_av`, `rain_cum` (meteorology); `lag_lumen` (lagged night lights); `id`, `plotm`, `ploty` (plot and fixed-effect identifiers); `province`, `lat`, `lon`, `mon`, `year`.

**Data availability:** [State whether the input files are included in this deposit, or where and under what terms they can be obtained.]
Extraction uses public base products plus custom crop-mask and preprocessed night-light inputs.
Provide accessible copies and their provenance as described in Section 4; asset identifiers alone do not grant access.

---

## 4. Upstream data construction

Python extracts the satellite inputs preceding the `SAR_SVN_rice_reprod.csv` handoff to Eugenia.
The Stata contribution documents her analysis datasets, sample restrictions, regressions and figures.
Concatenated Python exports do not reconstruct the handoff or final datasets: some joins, identifiers, lags and derived fields still lack complete provenance.

The archive contains `replication/README.md`, `replication/requirements.txt` and Python files; retain its `replication/` directory when unzipping beside this README.
See that README and the [GitHub extraction directory](https://github.com/sonleh96/adb-sar/tree/main/replication) for execution, inputs, historical conventions and validation results.
Historical notebooks remain in GitHub, outside the archive.

### 4.1 Satellite and reanalysis data

The table describes the recovered code.
Manuscript Section 4 identifies CAMS as the main PM2.5 source.
The channel script exports Eugenia's requested ESI and Aqua FPAR, excluding Terra FPAR, soil moisture and unused evapotranspiration.

| Variable | Source used by the code | Native resolution | Extraction and units |
|---|---|---|---|
| Rice areas | [JAXA Vietnam 2020 land-use and land-cover map, v23.09](https://www.eorc.jaxa.jp/ALOS/en/dataset/lulc/lulc_vnm_v2309_e.htm) | 10 m | Author-confirmed mosaicking of the categorical tiles, supplied by `prepare_crop_mask.py`. Upload the mosaic as band `b1`; extraction selects rice class 3. |
| Harvest calendar | Monsoon Asia Rice Calendar, Zhao et al. 2024, calendar year 2020 | About 55 km | `prepare_calendar.py` converts the Group and Cropping NetCDF files to rasters and samples harvest values at supplied coordinates. The reproductive-stage rule belongs to the later analysis construction and remains to be documented. |
| NDVI | `COPERNICUS/S2_HARMONIZED`, Sentinel-2 Level-1C | 10 m | `(B8-B4)/(B8+B4)`, monthly mean, minimum, and maximum. The recovered rice branch adds no cloud-quality mask. The candidate handoff field is `NDVI_mean` to `ndvi`. |
| RVI | `COPERNICUS/S1_GRD_FLOAT`, Sentinel-1A, descending IW, VV and VH | 10 m pixels | Linear-power `4*VH/(VV+VH)`, monthly mean. Mono-temporal Lee Sigma, kernel 3, with VOLUME terrain correction using SRTM. Candidate field: `RVI_mean` to `rvi`. |
| Aqua FPAR | `MODIS/061/MCD15A3H`, version 6.1 combined four-day product | 500 m | Retain pixels with `FparLai_QC` sensor bit 1 equal to 1 and SCF_QC bits 5-7 unequal to 4. Multiply `Fpar` by 0.01 and calculate monthly mean, minimum, and maximum. `FPAR_Aqua_mean` corresponds to handoff `fpar_aqua_mean`; the analysis should document its rename to `fpar`. |
| ESI, four-week | `projects/climate-engine/esi/4wk`, NASA-NOAA ESI via Climate Engine | About 4 km | Monthly mean, minimum, and maximum of band `ESI`. The four-week product is an input composite, not a four-week window computed by this script. Candidate field: `ESI_4wk_mean` to `esi_4wk_mean`. |
| PM2.5 | `ECMWF/CAMS/NRT` | About 44 km | Mean and maximum across images within the requested month window, using `particulate_matter_d_less_than_25_um_surface` multiplied by `1e9` to convert kg/m3 to micrograms/m3. Candidate fields: `PM25_mean` and `PM25_max` to `pm25_mean` and `pm25_max`. |
| Temperature | `ECMWF/ERA5_LAND/DAILY_AGGR` | About 11 km | Mean and maximum of the daily mean `temperature_2m` band, minus 273.15, in degrees Celsius. The maximum is not a maximum of daily temperature maxima. |
| Relative humidity | ERA5-Land temperature and dew point | About 11 km | Magnus expression below, evaluated from monthly mean temperature and monthly mean dew point. Output is a fraction, not a percentage. Candidate field: `Rel_humidity_mean` to `hum_av`. |
| Rainfall | ERA5-Land `total_precipitation_sum` | About 11 km | Sum across daily precipitation totals, in metres. Candidate field: `Precipitation_sum` to `rain_cum`. |
| Night lights | Monthly VIIRS Black Marble VNP46A3, prepared as `VNM_bm_YYYY_MM` | About 500 m in the source product | Author-confirmed Python preprocessing from `wb_nightlights_production`, adapted in `prepare_nightlights.py`: quality and land/water filtering, annual EOG lit masks, 0.1 radiance scaling, and linear monthly interpolation with extrapolation. Radiance is in nW/cm2/sr. Construction of the analysis lag remains a later step. |

Relative humidity is `exp((Td-T)*243.04*17.625 / ((T+243.04)*(Td+243.04)))`, with monthly mean temperature `T` and dew point `Td` in degrees Celsius.
This differs from averaging relative humidity calculated separately for each day.

[MCD15A3H](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD15A3H) selects the best Terra-Aqua observation within each four-day period.
The historical Aqua field filters this product's sensor bit; it does not use the separate MYD15 Aqua product.
Terra FPAR and soil moisture remain in the old handoff CSV but are excluded from revised exports.
Removing unused bands also removes their validity requirements, so new runs may retain previously omitted coordinates.

**Spatial and temporal conventions.**
The scripts sample EPSG:4326 at nominal 100 m spacing using a 10 m rice mask.
The grid represents sampling locations, not surveyed farms or native 100 m detail from coarse products.
Son's correction applies bicubic interpolation to native continuous CAMS, ERA5, Black Marble, ESI and Aqua FPAR bands before monthly reducers and crop masking.
FPAR quality flags are evaluated first; rice classes retain nearest-neighbor handling, and fine-resolution NDVI/RVI handling is unchanged.
See the [Earth Engine resampling guide](https://developers.google.com/earth-engine/guides/resample).
Replacing nearest-neighbor interpolation can change values and monthly extrema; outputs are not clipped to physical ranges.

The default `--date-mode historical` excludes the last calendar day because Earth Engine treats that date as the exclusive endpoint.
`--date-mode full-month` ends at the next month's first day and changes the data.
Use the reference sample's convention for historical comparisons.
Sampling drops locations with any null band.
The recovered branch in `process_datasets.ipynb`, revision `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`, cells 117 and 120, explicitly requests 2017.
Its nine-band stack combines RVI, CAMS PM2.5, ERA5 meteorology, Black Marble and elevation, excluding Sentinel-5P gases and wind.
Python follows that stack with the bicubic correction.

**Nightlights preprocessing.**
Son confirmed [wb_nightlights_production](https://github.com/sonleh96/wb_nightlights_production/tree/44f0c80ce8ecd89a4cea33f85efe7886c55faae1) as the Python source; see `replication/README.md` for numerical rules and inputs.
It interpolates across equally spaced months using the preceding cleaned December and current year, without spatial smoothing or the R-script outlier cutoff.
The adapted driver fixes the source's off-by-one export so January's filename contains January's data.
As in the Python source, negative interpolated and unresolved missing values become zero at export.
Include original granule and EOG mask versions with the data.

**Python execution.**
After the Section 1 setup, run these commands from the directory containing `replication/` to inspect one tile-month without cloud requests:

```powershell
python -m replication.extract_ndvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_rvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_channels --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

For 2017-2022 extraction, replace the example dates and tile with the verified study mapping; the paper's precise tile subset remains unverified.
Authenticate separately, check the plan and input access, then add `--project YOUR_PROJECT --submit`.
Supply accessible custom inputs with `--crop-mask-asset` and `--ntl-asset-prefix`.
Submission alone does not confirm completion or historical agreement.

### 4.2 Analysis sample and handoff

Manuscript Section 4.2 excludes Dong Thap and panels affected by negative NDVI or drought.
These are downstream restrictions, not extraction filters.
Eugenia's files must document reproductive-stage assignment, the drought definition and threshold, exclusion timing and table-specific samples.
Section 6 lists outstanding code for Tables A5 and A6.
`SAR_SVN_rice_reprod.csv` remains an intermediate handoff.

### 4.3 Fire data

Manuscript Section 4.6 and the analysis README specify MODIS FIRMS detections with channel 21/22 and 31 brightness temperatures in kelvin and FRP in megawatts.
File 2 uses `FRP_son.dta` and `lon-lat-adm1.csv`, which links locations to GADM 4.1 admin-1 units.
`prepare_fire_detections.py` reconstructs these inputs from standard science-quality FIRMS MODIS Collection 6.1 Terra/Aqua CSVs and GADM 4.1 admin-1 GeoJSON.
It preserves MW, kelvin and four-character UTC acquisition times, writing `FRP_son.csv`, optional `FRP_son.dta`, `lon-lat-adm1.csv` and a manifest of checksums, regions, policies and counts.
Default dates are inclusive 2017-01-01 through 2022-12-31, without confidence, seasonal or distance filters.
Polygon coverage assigns locations; duplicates, unassigned points and multiple matches fail unless explicitly permitted.
Myanmar's country label is `MYM`; its GADM IDs retain `MMR`.
The original preparation code remains unrecovered; historical field names, the southern China subset and additional filters need reconciliation with Eugenia's inputs.
See the extraction README for commands and [FIRMS archive documentation](https://firms.modaps.eosdis.nasa.gov/download/Readme.txt).

`extract_fire.py` retains two historical workflows:

- MODIS Terra `MODIS/061/MOD14A1` regional monthly FRP summaries, with a 0.1 scale factor and the source fire and land-quality masks.
- FIRMS T21 country summaries, using a separate raster collection and the original temporal and spatial reducers.

These summaries and `prepare_fire_distances.py` regional centroid distances differ from File 2's detections and fire-to-PM2.5-grid distances.
Do not substitute them for `FRP_son.dta` or `lon-lat-adm1.csv`.

### 4.4 Verification and items to resolve before publication

The extraction README records checks of command-line plans, methods, bounded archived samples and archive contents.
These do not establish full paper reproduction.
Before publication:

1. Confirm the historical extraction tile subset and remaining pre-handoff transformations, and retain the Black Marble granule and EOG mask versions with the data.
2. Reconcile the reconstructed fire schema, source-region selection, and any additional historical filtering with the analysis inputs.
3. Ensure the manuscript describes the corrected bicubic method and the recovered nightlights rules, including the corrected month selection.
4. Complete the author-owned Stata, figures, sample-definition, software-version, runtime, data-availability, citation, and licence entries in this README.
5. Eugenia uploads the reviewed README, matching extraction archive and analysis files to her Zenodo draft, then adds the published DOI to Methods or Code Availability.
   Son does not need Zenodo editing access.

---

## 5. Description of the do-files

### `1_Results-Panel.do`: summary statistics and panel fixed-effects results

**Input:** `reg_SVN_rice_SpatAuto_with_grid_IDs.dta`

Estimates PM2.5 associations with NDVI, RVI, fPAR and ESI using plot-by-month and plot-by-year fixed effects.
Dong Thap is excluded throughout; see the paper's justification.

- **Section 0:** sample setup and summary statistics (Table 1).
- **Section 1:** linear, quadratic and spline (knots at 15, 30, 50 µg/m³) models with meteorological controls (Panel A), and linear and quadratic models without them (Panel B).
  Standard errors clustered at the plot level.
- **Section 2:** the same models with wild cluster bootstrap p-values and confidence intervals, clustered at the PM2.5 grid level (~0.36°, 35 clusters).
  `hdfe` partials out fixed effects before `regress` because `boottest` cannot follow `reghdfe` with multiple absorbed effects.
  Standard errors are grid-clustered; PM2.5 p-values and confidence intervals use the wild bootstrap.
- **Section 3:** compares retained observations with singletons dropped by `reghdfe`.
- **Section 4:** leave-one-province-out sensitivity of the spline specification (the baseline row includes Dong Thap).

**Outputs:**

- `table1_summary_stats.csv`
- `master_clusterID_results.csv` (Panel A)
- `panelB_nomet_clusterID_results.csv` (Panel B)
- `master_wildboot_pm25grid_results.dta` / `.csv` (Panels A and B; Panel B rows labelled `lin_nomet` and `quad_nomet` in the `spec` column)
- `retained_vs_dropped_comparison.csv`
- `leave_one_province_out_spline_results.csv`
- `1_Results-Panel.log`

### `2_Results-Fire-ElasticNet-pmgrid.do`: fire instruments

**Inputs:** `reg_SVN_rice_SpatAuto_with_grid_IDs.dta`, `FRP_son.dta`, `lon-lat-adm1.csv`

1. Assigns plots to PM2.5 grid cells and extracts grid centroids.
2. Cleans fires and retains downwind months: February-April for China, Laos, Thailand, Myanmar and Cambodia; July-October for Indonesia and Malaysia.
   Placebo fires use the remaining upwind months.
   Myanmar's source code is `MYM`, not ISO `MMR`.
3. Applies 1/d and 1/d² decay from each fire to each grid centroid, aggregating by admin-1 source region and month for main and placebo data.
4. Builds the grid-by-month dataset.
5. Uses cross-validated elastic net on fixed-effect-residualised data to select regions predicting PM2.5, separately for FRP, brightness and T31 under each decay form.
6. Sums and averages selected regions' fire intensity to form instruments; placebo instruments use the same regions with wind-reversed fires.

**Outputs:**

- `rice_with_pm25grid.dta`, `grid_centroids.dta`
- `fires_clean_base.dta`, `fires_false_base.dta`
- `fire_decay_wide_clean.dta`, `fire_decay_wide_false.dta`
- `IV_pm-grid.dta` (analysis dataset used by file 3)
- `elasticnet_*_results.ster` (elastic net estimates)
- `2_Results-Fire-ElasticNet.log`, `elasticnetun.log`

### `3_Results-IV.do`: instrumental-variables results

**Input:** `IV_pm-grid.dta` (from file 2)

Estimates reduced forms, first stages and 2SLS for each outcome and instrument, with grid, month and year fixed effects and grid clustering.
Weak-instrument-robust inference uses Anderson-Rubin tests with wild cluster bootstrap, Webb weights and 999 replications.

- **Section A:** with meteorological controls.
- **Section B:** without meteorological controls.
- **Section C:** falsification using the placebo (wind-reversed) instruments, with and without controls.

**Outputs:**

- `iv_ar_boot_results.dta` / `.xlsx`, `iv_full_<outcome>.csv` (Section A)
- `iv_ar_boot_results_nomet.dta` / `.xlsx`, `iv_full_<outcome>_nomet.csv` (Section B)
- `iv_falsification_results.dta` / `.xlsx`, `iv_falsification_coefficients.csv` (Section C)
- `3_Results-IV.log`

### `4_Figures.do`: figures

**Inputs:** [ ]

[Short description of each figure produced.]

**Outputs:**

- [Figure 3 file name]
- [Figure A1 file name]

---

## 6. Mapping to the paper

### Main text

| Paper item | Do-file and section | Output file |
|---|---|---|
| Table 1: Summary statistics | `1_Results-Panel.do`, Section 0 | `table1_summary_stats.csv` |
| Table 2, Panel A: NDVI (cols 1, 3, 5: plot-level clusters) | `1_Results-Panel.do`, Section 1 | `master_clusterID_results.csv` |
| Table 2, Panel A: NDVI (cols 2, 4, 6: ~44 km grid clusters) | `1_Results-Panel.do`, Section 2 | `master_wildboot_pm25grid_results.csv` |
| Table 2, Panel B: NDVI without meteorological covariates (cols 1, 3) | `1_Results-Panel.do`, Section 1 | `panelB_nomet_clusterID_results.csv` |
| Table 2, Panel B: NDVI without meteorological covariates (cols 2, 4) | `1_Results-Panel.do`, Section 2 | `master_wildboot_pm25grid_results.csv` (`lin_nomet`, `quad_nomet`) |
| Table 3, Panel A: fPAR and ESI | `1_Results-Panel.do`, Sections 1 and 2 | `master_clusterID_results.csv`, `master_wildboot_pm25grid_results.csv` |
| Table 3, Panel B: fPAR and ESI without meteorological covariates | `1_Results-Panel.do`, Sections 1 and 2 | `panelB_nomet_clusterID_results.csv`, `master_wildboot_pm25grid_results.csv` (`lin_nomet`, `quad_nomet`) |
| Table 4: IV, NDVI, RVI, fPAR (instrument: `ln_av_bright2`) | `3_Results-IV.do`, Section A | `iv_full_ndvi.csv`, `iv_full_rvi.csv`, `iv_full_fpar.csv`, `iv_ar_boot_results.xlsx` |
| Figure 1: Study area | Made in QGIS 4.0.1 (not code-generated) | - |
| Figure 2: Fire source regions used in the instrument | Regions selected in `2_Results-Fire-ElasticNet-pmgrid.do` (elastic net, brightness 1/d²); map made in QGIS 4.0.1 | `elasticnet_bright_invd2_results.ster`, `2_Results-Fire-ElasticNet.log` |
| Figure 3: Fire activity and PM2.5 over time | `4_Figures.do` | [file name] |

### Supplementary information

| Paper item | Do-file and section | Output file |
|---|---|---|
| Table A1, Panel A: RVI | `1_Results-Panel.do`, Sections 1 and 2 | `master_clusterID_results.csv`, `master_wildboot_pm25grid_results.csv` |
| Table A1, Panel B: RVI without meteorological covariates | `1_Results-Panel.do`, Sections 1 and 2 | `panelB_nomet_clusterID_results.csv`, `master_wildboot_pm25grid_results.csv` (`lin_nomet`, `quad_nomet`) |
| Table A2: IV without meteorological controls | `3_Results-IV.do`, Section B | `iv_full_<outcome>_nomet.csv`, `iv_ar_boot_results_nomet.xlsx` |
| Table A3: IV falsification | `3_Results-IV.do`, Section C | `iv_falsification_coefficients.csv`, `iv_falsification_results.xlsx` |
| Table A4: Leave-one-province-out | `1_Results-Panel.do`, Section 4 | `leave_one_province_out_spline_results.csv` |
| Table A5: With and without Dong Thap (cols 3-4) | `1_Results-Panel.do`, Section 1 | `master_clusterID_results.csv` |
| Table A5: All 15 provinces (cols 1-2) | [code to be added] | [ ] |
| Table A6: Negative-NDVI and drought-affected panels | [code to be added] | [ ] |
| Table A7: Study sample versus singletons | `1_Results-Panel.do`, Section 3 | `retained_vs_dropped_comparison.csv` |
| Table A8: Candidate instruments | Instruments built in `2_Results-Fire-ElasticNet-pmgrid.do`; [regression code to be added] | [ ] |
| Figure A1: CAMS vs OWM PM2.5 | `4_Figures.do` | [file name] |

---

## 7. Licence

The authors must confirm the licence for their own code before publication.
The two vendored `gee_s1_ard` Python modules retain their upstream MIT licence and attribution in `replication/README.md` and the source headers.
The adapted nightlights code retains the MIT licence and attribution from Son's `wb_nightlights_production` repository.
Data remain subject to the terms of their original sources in Section 4.

## 8. Citation

Cite the paper and this repository:
[Citation and Zenodo DOI]
