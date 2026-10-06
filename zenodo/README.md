# Replication code: Air pollution and rice crop health: Evidence from Vietnam's Mekong Delta

**Authors:** Eugenia Go, Yohan Iddawela, Son Le, Elaine S. Tan (Asian Development Bank)
**Paper:** [Full citation once published]
**Code DOI:** [Zenodo DOI]
**Extraction-code contact:** Son Le, sonle.h96@gmail.com
**Analysis contact:** [Eugenia to confirm contact details]

This deposit combines the analysis contribution described below with the recovered Python extraction code.
The Stata file descriptions were supplied by Eugenia and have not been independently run in this extraction update.
The analysis estimates the relationship between PM2.5 exposure and rice crop health in Vietnam's Mekong Delta (2017-2022), using panel fixed-effects models and an instrumental-variables design based on transboundary fire activity.

---

## 1. Software requirements

Python extraction uses Python 3.11 and the dependencies in `replication/README.md`.
The Python archive does not include the analysis datasets or Stata files.
The following requirements apply to the Stata contribution.

- **Stata** [version, e.g. 18 MP].
  The elastic net (`elasticnet`) requires Stata 16 or later.
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

1. Place the Stata do-files and their input data in **one folder**.
   Unzip the Python extraction archive into that folder and retain its `replication/` subdirectory.
   Python extraction instructions are in Section 4 and `replication/README.md`.
2. Open Stata and change to that folder, e.g. `cd "C:/path/to/folder"`.
3. Run the do-files in order:

```stata
do 1_Results-Panel.do
do 2_Results-Fire-ElasticNet-pmgrid.do
do 3_Results-IV.do
do 4_Figures.do
```

All paths are relative to the folder Stata is opened in; no paths need editing.
Each file opens its own log.
File 3 requires the dataset created by file 2.
File 1 is independent of files 2 and 3.
[File 4 requires: …]

Random processes use fixed seeds (`12345`) for the wild cluster bootstrap and the elastic net cross-validation, so results are reproducible.

**Note on memory and runtime:** file 1 runs on over 10 million plot-month observations, and file 2 pairs every fire detection with every PM2.5 grid cell (`joinby`).
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
The base products are public, but the recovered code also depends on custom crop-mask and preprocessed night-light assets.
Their identifiers do not grant access; provide accessible inputs and document their provenance as described in Section 4.

---

## 4. Upstream data construction

The Python contribution supplies the recovered satellite extraction methods used before the handoff to Eugenia.
The handoff file is `SAR_SVN_rice_reprod.csv`.
Eugenia's subsequent construction of the analysis datasets, sample restrictions, regressions, and figures is documented in the Stata contribution.
Concatenating the Python exports alone does not reconstruct that handoff CSV or the final Stata datasets.
Some pre-handoff joins, identifiers, lags, and derived fields still lack a complete provenance record.

The extraction archive contains `replication/README.md` and Python files only.
Unzip it beside this README and the analysis files, retaining the `replication/` directory.
The detailed Python instructions, historical conventions, input requirements, and validation results are in `replication/README.md` and the [GitHub extraction directory](https://github.com/sonleh96/adb-sar/tree/main/replication).
Original notebooks remain historical source material in GitHub and are excluded from the extraction archive.

### 4.1 Satellite and reanalysis data

The following definitions describe the recovered code.
Section 4 of the supplied manuscript establishes CAMS as the paper's main PM2.5 source.
Eugenia confirmed inclusion of ESI and Aqua FPAR, exclusion of Terra FPAR, and no soil-moisture requirement.
The revised channel script therefore requests only ESI and Aqua FPAR.
It also removes the unused evapotranspiration export.

| Variable | Source used by the code | Native resolution | Extraction and units |
|---|---|---|---|
| Rice areas | JAXA Vietnam land-use and land-cover map, local 2020 rasters labelled `v23.09` | 10 m | Class 3 from band `b1` of the custom `LULC_VN` asset. Exact historical clipping, mosaic, and asset provenance still need confirmation. |
| Harvest calendar | Monsoon Asia Rice Calendar, Zhao et al. 2024, calendar year 2020 | About 55 km | `prepare_calendar.py` converts the Group and Cropping NetCDF files to rasters and samples harvest values at supplied coordinates. The reproductive-stage rule belongs to the later analysis construction and remains to be documented. |
| NDVI | `COPERNICUS/S2_HARMONIZED`, Sentinel-2 Level-1C | 10 m | `(B8-B4)/(B8+B4)`, monthly mean, minimum, and maximum. The recovered rice branch adds no cloud-quality mask. The candidate handoff field is `NDVI_mean` to `ndvi`. |
| RVI | `COPERNICUS/S1_GRD_FLOAT`, Sentinel-1A, descending IW, VV and VH | 10 m pixels | Linear-power `4*VH/(VV+VH)`, monthly mean. Mono-temporal Lee Sigma, kernel 3, with VOLUME terrain correction using SRTM. Candidate field: `RVI_mean` to `rvi`. |
| Aqua FPAR | `MODIS/061/MCD15A3H`, version 6.1 combined four-day product | 500 m | Retain pixels with `FparLai_QC` sensor bit 1 equal to 1 and SCF_QC bits 5-7 unequal to 4. Multiply `Fpar` by 0.01 and calculate monthly mean, minimum, and maximum. `FPAR_Aqua_mean` corresponds to handoff `fpar_aqua_mean`; the analysis should document its rename to `fpar`. |
| ESI, four-week | `projects/climate-engine/esi/4wk`, NASA-NOAA ESI via Climate Engine | About 4 km | Monthly mean, minimum, and maximum of band `ESI`. The four-week product is an input composite, not a four-week window computed by this script. Candidate field: `ESI_4wk_mean` to `esi_4wk_mean`. |
| PM2.5 | `ECMWF/CAMS/NRT` | About 44 km | Mean and maximum across images within the requested month window, using `particulate_matter_d_less_than_25_um_surface` multiplied by `1e9` to convert kg/m3 to micrograms/m3. Candidate fields: `PM25_mean` and `PM25_max` to `pm25_mean` and `pm25_max`. |
| Temperature | `ECMWF/ERA5_LAND/DAILY_AGGR` | About 11 km | Mean and maximum of the daily mean `temperature_2m` band, minus 273.15, in degrees Celsius. The maximum is not a maximum of daily temperature maxima. |
| Relative humidity | ERA5-Land temperature and dew point | About 11 km | Magnus expression below, evaluated from monthly mean temperature and monthly mean dew point. Output is a fraction, not a percentage. Candidate field: `Rel_humidity_mean` to `hum_av`. |
| Rainfall | ERA5-Land `total_precipitation_sum` | About 11 km | Sum across daily precipitation totals, in metres. Candidate field: `Precipitation_sum` to `rain_cum`. |
| Night lights | Preprocessed monthly VIIRS Black Marble assets `VNM_bm_YYYY_MM` | About 500 m in the source product | Sample band `b1` as `Luminosity`. The original Black Marble product version, cleaning, smoothing, units, and construction of the lag must be recovered or confirmed before claiming full reproduction. |

Relative humidity is `exp((Td-T)*243.04*17.625 / ((T+243.04)*(Td+243.04)))`, with monthly mean temperature `T` and dew point `Td` in degrees Celsius.
This differs from averaging relative humidity calculated separately for each day.

The [MCD15A3H catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD15A3H) describes a combined Terra-Aqua product that selects the best observation within each four-day period.
The historical Aqua field filters that combined product by the selected sensor bit.
It is not an extraction from the separate MYD15 Aqua product.
Terra FPAR and soil moisture remain columns in the old handoff CSV but are not requested or exported by the revised channel script.
Removing unused channels also removes their joint validity requirements, so a fresh run can retain coordinates omitted by the original larger stack.
Historical sample equivalence has not yet been established.

**Spatial and temporal conventions.**
The scripts request EPSG:4326 at a nominal 100 m scale and use the 10 m rice mask.
This grid defines sampling locations, not surveyed farm boundaries or new native 100 m information from coarser products.
The recovered extraction scripts reproject without an explicit interpolation method or area-aggregation reducer.
[Earth Engine defaults to nearest-neighbour resampling](https://developers.google.com/earth-engine/guides/resample).
The bicubic description in manuscript Section 4.7 therefore remains unresolved: provide the missing interpolation code or revise that description after author review.
The Python update preserves the recovered method.

The default `--date-mode historical` uses the last calendar day as Earth Engine's exclusive end date, omitting observations on that day.
`--date-mode full-month` uses the first day of the next month and changes the data.
Historical comparison must use the same convention as the reference sample.
Sampling drops locations with a null value in any band in the selected stack.
The recovered combined covariates script also contains Sentinel-5P gases with coverage beginning after 2017.
That literal branch cannot establish the source of nonempty 2017 handoff rows; the exact historical covariate-generation branch remains to be recovered.

**Python execution.**
Use Python 3.11 and install the execution dependencies listed in `replication/README.md`.
Run the following commands from the directory containing `replication/` to inspect one tile-month without cloud requests:

```powershell
python -m replication.extract_ndvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_rvi --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
python -m replication.extract_channels --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

For the historical run, replace the example with the verified tile mapping and requested 2017-2022 month range.
The precise paper tile subset has not yet been verified.
Authenticate separately, then add `--project YOUR_PROJECT --submit` only after checking the plan and input access.
Use `--crop-mask-asset` and `--ntl-asset-prefix` to supply accessible copies of the custom inputs.
The scripts do not authenticate automatically.
An export submission is not evidence that the task completed or matched the historical data.

### 4.2 Analysis sample and handoff

Manuscript Section 4.2 describes Dong Thap exclusion and panel-level exclusions for negative NDVI and drought.
The extraction scripts do not apply those downstream sample restrictions.
Eugenia's analysis files must document the reproductive-stage assignment, the drought definition and threshold, the timing of each exclusion, and the table-specific samples.
Section 6 identifies the remaining analysis-code entries for Tables A5 and A6.
The original `SAR_SVN_rice_reprod.csv` is an intermediate handoff, not a replacement for that analysis construction.

### 4.3 Fire data

Manuscript Section 4.6 and the analysis README describe MODIS FIRMS detection-level brightness temperatures for channels 21/22 and 31, in kelvin, and fire radiative power, in megawatts.
File 2 consumes `FRP_son.dta` and the fire-location lookup `lon-lat-adm1.csv` with GADM 4.1 admin-1 identifiers.
The original point-download, selection, and administrative-assignment code has not been recovered in this repository.
The exact collection, download dates, geographical bounds, confidence filters, and boundary-assignment rule remain to be supplied with those inputs.

Two recovered historical fire workflows are provided in `extract_fire.py`:

- MODIS Terra `MODIS/061/MOD14A1` regional monthly FRP summaries, with a 0.1 scale factor and the source fire and land-quality masks.
- FIRMS T21 country summaries, using a separate raster collection and the original temporal and spatial reducers.

Neither workflow reconstructs the detection-level table with FRP, brightness, and T31 used by the current Stata instruments.
The regional centroid distances from `prepare_fire_distances.py` likewise differ from the fire-to-PM2.5-grid distances described for File 2.
These legacy outputs must not be substituted for `FRP_son.dta` or `lon-lat-adm1.csv`.

### 4.4 Verification and items to resolve before publication

Local validation covers command-line plans, method checks, bounded archived-data comparisons, and the contents of the Python archive.
It does not establish full reproduction of the paper.
On 6 October 2026, the saved Earth Engine credential returned `invalid_grant`; no new cloud extraction was completed.
The extraction README records each check and its scope.

The remaining items are:

1. Restore Earth Engine authentication and custom-input access, then compare one tile-month with an independent frozen extraction sample.
2. Recover the Black Marble preprocessing, exact JAXA mask construction, historical tile subset, 2017 covariate branch, and remaining pre-handoff transformations, or document accessible frozen inputs and their provenance where appropriate.
3. Obtain the detection-level FIRMS preparation and admin-1 lookup code used for the current fire instruments.
4. Reconcile manuscript Section 4.7 with the actual interpolation method.
5. Complete the author-owned Stata, figures, sample-definition, software-version, runtime, data-availability, citation, and licence entries in this README.
6. Eugenia uploads the reviewed README, matching extraction archive, and analysis contribution to her existing Zenodo draft, then adds the published DOI to the manuscript's Methods or Code Availability section.

Zenodo editing access for Son is not required for that handoff.

---

## 5. Description of the do-files

### `1_Results-Panel.do`: summary statistics and panel fixed-effects results

**Input:** `reg_SVN_rice_SpatAuto_with_grid_IDs.dta`

Estimates the relationship between PM2.5 and crop health (NDVI, RVI, fPAR, ESI) with plot-by-month and plot-by-year fixed effects.
Dong Thap province is excluded throughout (see the paper for the justification).

- **Section 0:** sample setup and summary statistics (Table 1).
- **Section 1:** linear, quadratic and spline (knots at 15, 30, 50 µg/m³) models with meteorological controls (Panel A), and linear and quadratic models without them (Panel B).
  Standard errors clustered at the plot level.
- **Section 2:** the same models with wild cluster bootstrap p-values and confidence intervals, clustered at the PM2.5 grid level (~0.36°, 35 clusters).
  Fixed effects are partialled out with `hdfe` before `regress`, as `boottest` cannot run directly after `reghdfe` with multiple absorbed fixed effects.
  Reported standard errors are conventional grid-clustered SEs; p-values and CIs for the PM2.5 terms are from the wild bootstrap.
- **Section 3:** compares observations retained by `reghdfe` with those dropped as singletons.
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

1. Assigns each rice plot to a PM2.5 grid cell and extracts the grid centroids.
2. Cleans the fire data and assigns a wind-direction indicator: fires count only in months when the Mekong Delta is downwind of their source (February-April for China, Laos, Thailand, Myanmar and Cambodia; July-October for Indonesia and Malaysia).
   A placebo version reverses this, counting fires only in the remaining (upwind) months.
   *Note:* Myanmar is coded `MYM` in the source data (not the ISO code `MMR`).
3. Computes distance-decayed fire intensity (1/d and 1/d²) from every fire to every grid-cell centroid, aggregated by source region (admin-1 unit) and month, for both the main and placebo versions.
4. Builds the grid-by-month analysis dataset.
5. Uses elastic net (cross-validation) on fixed-effect-residualised data to select the source regions that predict PM2.5, separately for FRP, brightness and T31 under each decay form.
6. Constructs the instruments as the total and mean of the selected regions' fire intensity, and the placebo instruments from the same regions using the wind-reversed fires.

**Outputs:**

- `rice_with_pm25grid.dta`, `grid_centroids.dta`
- `fires_clean_base.dta`, `fires_false_base.dta`
- `fire_decay_wide_clean.dta`, `fire_decay_wide_false.dta`
- `IV_pm-grid.dta` (analysis dataset used by file 3)
- `elasticnet_*_results.ster` (elastic net estimates)
- `2_Results-Fire-ElasticNet.log`, `elasticnetun.log`

### `3_Results-IV.do`: instrumental-variables results

**Input:** `IV_pm-grid.dta` (from file 2)

For each outcome and instrument, estimates the reduced form, first stage and 2SLS with grid, month and year fixed effects, clustered at the grid level.
Weak-instrument-robust inference uses the Anderson-Rubin test with wild cluster bootstrap (Webb weights, 999 replications).

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

### Supplementary Information

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
Data remain subject to the terms of their original sources in Section 4.

## 8. Citation

If you use this code, please cite the paper and this repository:
[Citation and Zenodo DOI]
