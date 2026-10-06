# Extraction terms

| Term | Meaning in this repository |
| --- | --- |
| Handoff CSV | `SAR_SVN_rice_reprod.csv`, supplied to Eugenia with fields derived beyond raw extraction. |
| Extraction archive | ZIP of the extraction README, requirements, and Python files; excludes data, notebooks, and Stata files. |
| Combined deposit README | `zenodo/README.md`, supplied to Eugenia with the extraction archive. |
| Aqua FPAR | MCD15A3H pixels with QC sensor bit 1 equal to 1; not the MYD15 product. |
| Historical date mode | Uses the last calendar day as the exclusive end date. |
| Legacy fire summaries | Regional MOD14A1 FRP or country-level FIRMS T21 summaries. |
| Paper fire detections | Detection-level FRP, brightness, and T31 inputs for `FRP_son.dta`. |
| Reconstructed fire preparation | Standard FIRMS MODIS C6.1 CSVs assigned to GADM 4.1 admin-1 polygons; historical schema and selection remain unconfirmed. |
| Bicubic correction | Resamples coarse continuous sources before monthly reducers; classes and QC retain nearest-neighbor handling. |
| Recovered covariate branch | Nine-band stack in `process_datasets.ipynb`, cell 120 at `4b8944d8f86c1b917bdf0f52397540ed9b10e0d8`; excludes Sentinel-5P and wind. |
| Black Marble preprocessing | Author-confirmed Python cleaning and gap filling from `wb_nightlights_production`, adapted locally with corrected month indexing. |
| JAXA mosaic | Vietnam 2020 v23.09 categorical mosaic; rice is class 3. |
