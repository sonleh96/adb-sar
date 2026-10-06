# adb-sar

Satellite and environmental extraction code supporting the agricultural analysis.
The Python workflow and its execution instructions are in [replication/README.md](replication/README.md).
The release builder includes that README and Python files only.
The revised [combined Zenodo README](zenodo/README.md) incorporates Eugenia's manuscript data description and preserves her analysis instructions.
The channel extraction includes ESI and Aqua FPAR, with Terra FPAR, soil moisture, and unused ET removed from the sampled stack.

The extraction contribution ends at the data supplied to Eugenia, including `SAR_SVN_rice_reprod.csv`.
Her subsequent construction of analysis or training datasets, Stata results, and figures belongs to the accompanying analysis replication files.

This is a preparation release.
CAMS PM2.5 and the paper's detection-level MODIS fire metrics are now confirmed, but the point-fire preparation and nighttime lights preprocessing remain missing.
Access to the exact custom inputs, the 2017 covariate branch, historical comparison, and the manuscript's bicubic description still need resolution.
It has not been submitted to Zenodo and does not yet establish complete reproduction of the delivered CSV.
Original notebooks remain as historical source material; production commands use the Python modules under `replication/`.

For input data and assistance, contact Son Le at sonle.h96@gmail.com.
