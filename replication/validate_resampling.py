"""Validate corrected extraction graphs using the real Earth Engine SDK.

Checks the source bands entering bicubic interpolation, its position before
monthly reducers and crop masking, and the recovered 2017 covariate stack.
Only SDK algorithm metadata is supplied locally; no exports are submitted.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from .common import rice_mask
from .config import ExtractionConfig
from .extract_channels import build_month_image as channels_image
from .extract_covariates import build_month_image as covariates_image
from .extract_ndvi import build_month_image as ndvi_image
from .extract_rvi import build_month_image as rvi_image


def run_resampling_check() -> dict[str, object]:
    import ee
    from ee.apitestcase import GetAlgorithms

    graphs = {}
    try:
        with patch.object(ee.data, "_install_cloud_api_resource"), patch.object(
            ee.data, "getAlgorithms", return_value=GetAlgorithms()
        ), patch.object(ee, "_InitializeDeprecatedAssets"):
            ee.Initialize(credentials=None, project="offline-validation")
            config = ExtractionConfig("2017-01", "2017-01", "check")
            roi = ee.Geometry.BBox(105, 10, 105.5, 10.5)
            mask = rice_mask(ee, "projects/example/assets/rice", roi)
            arguments = dict(start="2017-01-01", exclusive_end="2017-01-31")
            images = {
                "covariates": covariates_image(
                    ee, config, roi, mask, **arguments, month="2017-01",
                    ntl_asset_prefix="projects/example/assets/bm",
                ),
                "channels": channels_image(ee, config, roi, mask, **arguments),
                "ndvi": ndvi_image(ee, config, roi, mask, **arguments),
                "rvi": rvi_image(ee, config, roi, mask, **arguments, include_sar_stats=True),
                "rice_mask": mask,
            }
            graphs = {name: json.loads(image.serialize()) for name, image in images.items()}
    finally:
        ee.Reset()

    errors = []
    summaries = {}
    expected_sources = {
        "covariates": {
            "ECMWF/CAMS/NRT": ["particulate_matter_d_less_than_25_um_surface"],
            "ECMWF/ERA5_LAND/DAILY_AGGR": [
                "temperature_2m", "dewpoint_temperature_2m", "total_precipitation_sum",
            ],
            "projects/example/assets/bm/VNM_bm_2017_01": ["b1"],
        },
        "channels": {"projects/climate-engine/esi/4wk": ["ESI"], "MODIS/061/MCD15A3H": ["Fpar"]},
        "ndvi": {}, "rvi": {}, "rice_mask": {},
    }
    for workflow, graph in graphs.items():
        values = graph["values"]

        def resolve(node):
            while isinstance(node, dict) and "valueReference" in node:
                node = values[node["valueReference"]]
            return node

        def walk(node):
            node = resolve(node)
            if isinstance(node, dict):
                if "functionInvocationValue" in node:
                    yield node["functionInvocationValue"]
                if "functionDefinitionValue" in node:
                    yield from walk(values[node["functionDefinitionValue"]["body"]])
                else:
                    for child in node.values():
                        yield from walk(child)
            elif isinstance(node, list):
                for child in node:
                    yield from walk(child)

        def call(node):
            return resolve(node).get("functionInvocationValue", {})

        def constant(node):
            node = resolve(node)
            if "arrayValue" in node:
                return [constant(value) for value in node["arrayValue"]["values"]]
            return node.get("constantValue")

        root = values[graph["result"]]
        calls = list(walk(root))
        sources = {}
        for entry in calls:
            name, args = entry["functionName"], entry["arguments"]
            if name == "Collection.map":
                body = list(walk(args["baseAlgorithm"]))
                bicubic = [c for c in body if c["functionName"] == "Image.resample"
                           and constant(c["arguments"]["mode"]) == "bicubic"]
                if not bicubic:
                    continue
                definition = resolve(args["baseAlgorithm"])["functionDefinitionValue"]
                masked = call(values[definition["body"]])
                projected = call(masked.get("arguments", {}).get("image", {}))
                resampled = call(projected.get("arguments", {}).get("image", {}))
                projection = call(projected.get("arguments", {}).get("crs", {}))
                if (masked.get("functionName") != "Image.updateMask"
                        or projected.get("functionName") != "Image.reproject"
                        or constant(projected["arguments"].get("scale", {})) != 100
                        or constant(projection.get("arguments", {}).get("crs", {})) != "EPSG:4326"
                        or resampled.get("functionName") != "Image.resample"):
                    errors.append(f"{workflow}: source resampling must precede target projection and crop mask")
                upstream = call(args["collection"])
                selection = None
                if upstream.get("functionName") == "Collection.map":
                    definition = resolve(upstream["arguments"]["baseAlgorithm"])["functionDefinitionValue"]
                    selection = call(values[definition["body"]])
                if not selection or selection.get("functionName") != "Image.select":
                    errors.append(f"{workflow}: bicubic input was not selected native science bands")
                    continue
                bands = constant(selection["arguments"]["bandSelectors"])
                loaded = [c for c in walk(args["collection"]) if c["functionName"] == "ImageCollection.load"]
                for collection in loaded:
                    sources[constant(collection["arguments"]["id"])] = bands
            if name == "Image.resample" and constant(args["mode"]) == "bicubic":
                input_node = resolve(args["image"])
                if "argumentReference" in input_node:
                    continue
                selected = call(input_node)
                if selected.get("functionName") != "Image.select":
                    errors.append(f"{workflow}: bicubic was applied after a composite or crop mask")
                    continue
                loaded = call(selected["arguments"]["input"])
                if loaded.get("functionName") != "Image.load":
                    errors.append(f"{workflow}: direct bicubic input does not retain its native projection")
                    continue
                sources[constant(loaded["arguments"]["id"])] = constant(selected["arguments"]["bandSelectors"])
        if sources != expected_sources[workflow]:
            errors.append(f"{workflow}: wrong bicubic sources or source bands: {sources}")
        datasets = sorted({constant(c["arguments"]["id"]) for c in calls
                           if c["functionName"] == "ImageCollection.load"})
        if workflow == "covariates" and datasets != [
            "COPERNICUS/S1_GRD_FLOAT", "ECMWF/CAMS/NRT", "ECMWF/ERA5_LAND/DAILY_AGGR",
        ]:
            errors.append("Recovered covariate graph contains missing or unused collections")
        if workflow == "rice_mask" and any(c["functionName"] == "Image.resample" for c in calls):
            errors.append("Categorical rice mask was interpolated")
        summaries[workflow] = {"bicubic_sources": sources, "collections": datasets}
    return {"status": "fail" if errors else "pass", "errors": errors, "graphs": summaries,
            "earthengine_api_version": ee.__version__,
            "scope": "Serialized production graphs, not remote pixel comparisons"}


def main() -> int:
    result = run_resampling_check()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
