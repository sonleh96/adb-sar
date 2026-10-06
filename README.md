# adb-sar

Satellite and environmental extraction code supporting the agricultural analysis.
The Python workflow and its execution instructions are in [replication/README.md](replication/README.md).
The release builder includes that README, `requirements.txt`, and Python files.
The revised [combined Zenodo README](zenodo/README.md) incorporates Eugenia's manuscript data description and preserves her analysis instructions.
The channel extraction includes ESI and Aqua FPAR, with Terra FPAR, soil moisture, and unused ET removed from the sampled stack.

The extraction contribution ends at the data supplied to Eugenia, including `SAR_SVN_rice_reprod.csv`.
Her subsequent construction of analysis or training datasets, Stata results, and figures belongs to the accompanying analysis replication files.

The package includes bicubic upsampling of coarse continuous inputs, a reconstructed MODIS detection-level fire workflow, JAXA Vietnam 2020 v23.09 mosaicking, and a local adaptation of the original Python Black Marble preprocessing.
The historical 2017 covariate branch was recovered from `process_datasets.ipynb` at revision `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`, cell 120.
It excludes the Sentinel-5P and wind bands reintroduced by a later annotation rewrite.
The corrected resampling and nightlights month selection can change values relative to earlier outputs.
Exact historical input selections, remaining pre-handoff transformations, and the reconstructed fire schema still require reconciliation with the authors' analysis files.
The package has not been submitted to Zenodo.
Original notebooks remain as historical source material; production commands use the Python modules under `replication/`.
The [research notebook guide](NOTEBOOKS.md) explains the annotated notebooks, their inputs, historical branches, and execution status.

## Setup

Use Python 3.11 for the tested dependency versions.
Git and Python must be installed before running the commands below.
The root [requirements.txt](requirements.txt) installs the dependencies for the Python extraction and local preprocessing modules through [replication/requirements.txt](replication/requirements.txt).
These files pin direct dependencies; they are not a complete lockfile of transitive dependencies.

Clone the repository and enter its directory:

```shell
git clone https://github.com/sonleh96/adb-sar.git
cd adb-sar
```

On Windows, run these commands in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m replication.validate_sample --self-test
.\.venv\Scripts\python.exe -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

On Linux or macOS:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m replication.validate_sample --self-test
.venv/bin/python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01
```

The self-test checks local method definitions, and the last command prints a one-tile, one-month extraction plan.
Neither command authenticates or starts Earth Engine exports.
Commands below use `python`; run them with the virtual environment's Python executable shown above, or activate that environment first.

## Data access and extraction

Supply the local rasters, NetCDF calendars, administrative boundaries, and satellite inputs described in [replication/README.md](replication/README.md#required-inputs).
These data and credentials are supplied separately from the repository.
For Earth Engine exports, authenticate with your own account and use a registered Google Cloud project that can access your crop-mask and monthly nightlights assets.
On Windows, authenticate with `.\.venv\Scripts\earthengine.exe authenticate`; on Linux or macOS, use `.venv/bin/earthengine authenticate`.

After checking the dry-run plan, explicitly request an export:

```shell
python -m replication.extract_covariates --tile-id N10E105_0_1 --start-month 2019-01 --end-month 2019-01 --project YOUR_PROJECT --crop-mask-asset YOUR_CROP_MASK_ASSET --ntl-asset-prefix YOUR_MONTHLY_NTL_ASSET_FOLDER --submit
```

See [the extraction instructions](replication/README.md#execution) for NDVI, RVI, ESI/Aqua FPAR, fire, calendar, and local preparation commands.
The [notebook guide](NOTEBOOKS.md) lists additional dependencies and inputs for historical notebook experiments.
The optional OpenWeather notebook reads `OPENWEATHER_API_KEY` from your environment; configure it privately before running its API cells.
Keep credentials out of source files and saved notebook outputs.

## Preparing the code archive

```shell
python -m replication.build_release --output release_outputs/adb-sar-extraction-preparation.zip
```

The ZIP contains `replication/README.md`, `replication/requirements.txt`, and Python source files.
After unzipping, create a Python 3.11 environment and install with `python -m pip install -r replication/requirements.txt` from the directory containing `replication/`.
The [combined deposit README](zenodo/README.md) documents the accompanying Stata analysis contribution.

For input data and assistance, contact Son Le at sonle.h96@gmail.com.
