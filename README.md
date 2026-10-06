# adb-sar

Satellite and environmental extraction code supporting the agricultural analysis.
The Python workflow and its execution instructions are in [replication/README.md](replication/README.md).
The release builder includes that README and Python files only.
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

For input data and assistance, contact Son Le at sonle.h96@gmail.com.
