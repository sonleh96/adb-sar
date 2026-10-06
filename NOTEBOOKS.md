# Research notebook guide

Historical research workflows and experiments.
Use the [Python extraction guide](replication/README.md) for production; notebooks are excluded from the Zenodo code archive.

## Notebook map

| Notebook | Purpose | Reading and execution notes |
| --- | --- | --- |
| [process_datasets.ipynb](process_datasets.ipynb) | Uploads and crop-specific extraction experiments | Branches differ from the recovered paper workflow. Cells may authenticate, upload, download, or export. |
| [extract_channels.ipynb](extract_channels.ipynb) | Channel experiments and rice calendars | Includes excluded channels and historical georeferencing/DOY conventions. |
| [split_jaxa_tiles.ipynb](split_jaxa_tiles.ipynb) | Four bounds per JAXA tile | Writes JSON bounds, not split rasters or a crop-mask mosaic. Checked against all 60 tiles. |
| [owm.ipynb](owm.ipynb) | OpenWeather sample and district experiments | Requires `OPENWEATHER_API_KEY`. Sample aggregation excludes district files. |
| [draw_paper_figures.ipynb](draw_paper_figures.ipynb) | Historical maps | Retains two original images; verify inputs, CRS, and manuscript relevance. |
| [spatial_model.ipynb](spatial_model.ipynb) | Spatial-model experiments | Records unfinished fits and memory failures; separate from final Stata analysis. |

## What was cleaned

Annotations cover purpose, dependencies, inputs, outputs, and historical quirks.
Empty cells, tracebacks, repetitive logs, and stale execution counts were removed; useful historical outputs remain labelled.
Calculations and branch order are preserved.
OpenWeather now uses an environment credential, HTTPS, and basename coordinate parsing; JAXA uses portable paths.

## Original versions and provenance

Originals are at [19430e7](https://github.com/sonleh96/adb-sar/tree/19430e7614eeb976451240a9875a2fd81c2c8da5).
Source-cell metadata records original one-based positions; documentation references use the cited revisions.
The local snapshot and checksum inventory are in `release_outputs/notebook-cleanup-2026-10-06/`, with OpenWeather credentials redacted.
The snapshot includes nine unedited local-only notebooks and is excluded from GitHub and Zenodo.

## Verification and running

All six pass notebook-format and transformed Python syntax checks.
JAXA produced 240 bounds from 60 rasters, matching direct metadata within `1e-10` degrees.
OpenWeather passed local credential and aggregation checks, including a UTC-to-local month boundary and known mean, without API requests.
Other notebooks were not rerun because they require cloud operations, large datasets, or unfinished model fits.

Repeat format and syntax checks with `nbformat` and IPython:

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

Open notebooks from the repository root in Jupyter or a compatible editor.
Supply the listed dependencies and inputs, then check branch dates, output paths, and external operations before running.
