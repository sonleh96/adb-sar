# Research notebook guide

These notebooks document the research workflow and its exploratory branches.
The production extraction commands and Zenodo code archive remain in [replication/README.md](replication/README.md).
The notebook cleanup does not add notebooks to that archive or change its Python methods.

## Notebook map

| Notebook | Purpose | Reading and execution notes |
| --- | --- | --- |
| [process_datasets.ipynb](process_datasets.ipynb) | Earth Engine input uploads, extraction experiments, and crop-specific branches | Read each branch's scope before running it; authentication, uploads, downloads, and export cells have external effects. The annotated combined branch differs from the recovered paper covariate branch in the Python package. |
| [extract_channels.ipynb](extract_channels.ipynb) | Historical ESI/FPAR and additional-channel experiments, followed by rice-calendar preparation | The historical channel stack contains variables excluded from the current paper package. Calendar sections explain the retained georeferencing and day-of-year/month conventions. |
| [split_jaxa_tiles.ipynb](split_jaxa_tiles.ipynb) | Four geographic extraction bounds per JAXA tile | Produces a JSON bounds lookup, not split raster files or a crop-mask mosaic. The code cells were checked against all 60 original tiles. |
| [owm.ipynb](owm.ipynb) | OpenWeather comparison data for sampled locations and a separate district experiment | Reads `OPENWEATHER_API_KEY` from the environment. The 2022 sample aggregation does not consume the district-branch files. |
| [draw_paper_figures.ipynb](draw_paper_figures.ipynb) | Historical map preparation and plotting | The two retained map images are original saved outputs, not newly reproduced paper figures. Read the CRS and input-file notes. |
| [spatial_model.ipynb](spatial_model.ipynb) | Experimental spatial-model preprocessing and alternatives | Includes unfinished model attempts and an earlier memory-allocation failure. It is not the final Stata analysis contribution. |

## What was cleaned

The notebooks now have purpose, environment, input/output, and section annotations.
Empty cells, raw tracebacks, repetitive logs, and stale execution counts were removed.
Useful historical maps and bounded table or memory summaries were retained with context.
Their presence does not mean the analysis was rerun.

Research calculations and branch order were preserved.
The OpenWeather notebook now reads its credential from the environment, uses HTTPS, and parses coordinates from file basenames rather than whole Windows paths.
The JAXA notebook uses portable path handling and the current local input-folder layout.
Original quirks such as positional resume slices, date bounds, model failures, and alternative crop masks are explained rather than silently rewritten.

## Original versions and provenance

The original tracked notebooks remain available at [revision 19430e7](https://github.com/sonleh96/adb-sar/tree/19430e7614eeb976451240a9875a2fd81c2c8da5).
Each retained source cell records its original one-based cell number in metadata.
Historical cell-number references in the extraction documentation refer to the cited original revisions, not the new annotated positions.
A byte-preserved local snapshot and SHA-256 inventory were also saved under `release_outputs/notebook-cleanup-2026-10-06/`.
That local snapshot is not part of the GitHub update or the Zenodo code archive.

The two untracked root notebooks and seven ignored analysis notebooks remain outside this cleanup's default scope.
They are included in the local original-file snapshot for preservation.

## Verification and running

All six edited notebooks were checked with `nbformat.validate` and Python AST parsing after IPython input transformation.
The JAXA code cells produced 240 subtiles from all 60 original rasters in a temporary output directory; every bound matched a direct raster-metadata calculation within `1e-10` degrees.
The OpenWeather credential guards and local JSON aggregation were checked without API requests, including a UTC-to-local month boundary and a known monthly mean.
The other notebooks were not executed end-to-end because they contain cloud operations, large local-data processing, or expensive unfinished model experiments.

To repeat structural and syntax checks in an environment with `nbformat` and IPython:

```python
import ast
from pathlib import Path
import nbformat
from IPython.core.inputtransformer2 import TransformerManager

transformer = TransformerManager()
names = (
    "process_datasets.ipynb", "extract_channels.ipynb", "split_jaxa_tiles.ipynb",
    "owm.ipynb", "draw_paper_figures.ipynb", "spatial_model.ipynb",
)
for name in names:
    notebook = nbformat.read(Path(name), as_version=4)
    nbformat.validate(notebook)
    for cell in notebook.cells:
        if cell.cell_type == "code":
            ast.parse(transformer.transform_cell(cell.source))
    print(f"Checked {name}")
```

For execution, open a notebook in Jupyter or a compatible editor, start from the repository root, and supply the dependencies and local files named in its setup section.
Review its branch-specific date ranges, file destinations, and external-operation cells before running it.
Saved figures and tables are labelled as historical; new results should come from a deliberately configured run.
