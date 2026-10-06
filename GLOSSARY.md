# Extraction terms

| Term | Meaning in this repository |
| --- | --- |
| Handoff CSV | `SAR_SVN_rice_reprod.csv`, supplied to Eugenia before her subsequent analysis-data construction. It includes derived fields beyond the raw extraction exports. |
| Extraction archive | The ZIP built from `replication/README.md` and Python files. It excludes data, notebooks, and the Stata contribution. |
| Combined deposit README | `zenodo/README.md`, edited from Eugenia's attachment for upload beside her analysis files and the extraction archive. |
| Aqua FPAR | Aqua-selected pixels from the combined `MODIS/061/MCD15A3H` product, identified by QC sensor bit 1. It does not mean a switch to MYD15. |
| Historical date mode | The last calendar day is passed as an exclusive date bound, matching the recovered notebooks. |
| Legacy fire summaries | Regional MOD14A1 FRP or country FIRMS T21 summaries from the recovered notebooks. |
| Paper fire detections | The detection-level FRP, brightness, and T31 inputs described for `FRP_son.dta`, distinct from the legacy fire summaries. |
| Reconstructed fire preparation | New local code reading standard FIRMS MODIS Collection 6.1 CSVs and assigning GADM 4.1 admin-1 polygons; its schema and input selection need reconciliation with the historical Stata inputs. |
| Bicubic correction | Continuous coarse source images are resampled before monthly reducers; categorical crop classes and quality flags retain nearest-neighbor handling. |
| Recovered covariate branch | The nine-band stack in `process_datasets.ipynb`, cell 120 at revision `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`, with Sentinel-5P and wind excluded. |
| Black Marble preprocessing | The author-confirmed Python cleaning and monthly gap-filling pipeline from `wb_nightlights_production`, adapted for local files and corrected month selection. |
| JAXA mosaic | A categorical mosaic of Vietnam 2020 v23.09 land-cover tiles; class 3 is selected as rice during extraction. |
