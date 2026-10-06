"""Check channel graph construction with the Earth Engine SDK's test metadata.

The optional check needs the SDK's bundled ``ee/tests/algorithms.json``.
It evaluates serialized scalar QC expressions locally, not remote pixels.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from .config import ExtractionConfig
from .extract_channels import build_month_image


def run_channel_graph_check() -> dict[str, object]:
    try:
        import ee
        from ee.apitestcase import GetAlgorithms

        algorithms = GetAlgorithms()
    except (ImportError, OSError, ValueError) as exc:
        raise RuntimeError(
            "Channel graph checks require earthengine-api with its bundled "
            "ee/tests/algorithms.json; verified with earthengine-api==0.1.401."
        ) from exc

    # Replace only SDK metadata/network setup; our image builder runs unchanged.
    try:
        with patch.object(ee.data, "_install_cloud_api_resource"), patch.object(
            ee.data, "getAlgorithms", return_value=algorithms
        ), patch.object(ee, "_InitializeDeprecatedAssets"):
            ee.Initialize(credentials=None, project="offline-validation")
            image = build_month_image(
                ee, ExtractionConfig("2017-01", "2017-01", "dry-run"),
                ee.Geometry.BBox(105, 10, 105.5, 10.5), ee.Image.constant(1),
                start="2017-01-01", exclusive_end="2017-01-31",
            )
            graph = json.loads(image.serialize())
    except AttributeError as exc:
        raise RuntimeError("Earth Engine SDK lacks the offline graph-check interface.") from exc
    finally:
        ee.Reset()

    values = graph["values"]

    def walk(node):
        if isinstance(node, dict):
            if "functionInvocationValue" in node:
                yield node["functionInvocationValue"]
            for child in node.values():
                yield from walk(child)
        elif isinstance(node, list):
            for child in node:
                yield from walk(child)

    def evaluate(node, qc):
        if "valueReference" in node:
            return evaluate(values[node["valueReference"]], qc)
        if "constantValue" in node:
            return node["constantValue"]
        call = node["functionInvocationValue"]
        name, args = call["functionName"], call["arguments"]
        if name == "Image.select":
            if args["bandSelectors"]["constantValue"] != ["FparLai_QC"]:
                raise RuntimeError("QC expression selects an unexpected band")
            return qc
        if name == "Image.constant":
            return evaluate(args["value"], qc)
        left = evaluate(args["image1"], qc)
        right = evaluate(args["image2"], qc)
        operations = {
            "Image.rightShift": lambda: left >> right,
            "Image.bitwiseAnd": lambda: left & right,
            "Image.eq": lambda: left == right,
            "Image.neq": lambda: left != right,
            "Image.and": lambda: bool(left and right),
        }
        return operations[name]()

    calls = list(walk(graph))
    datasets = [
        call["arguments"]["id"]["constantValue"]
        for call in calls if call["functionName"] == "ImageCollection.load"
    ]
    bands = [
        name for call in calls if call["functionName"] == "Image.rename"
        for name in call["arguments"]["names"]["constantValue"]
    ]
    errors = []
    if sorted(datasets) != ["MODIS/061/MCD15A3H", "projects/climate-engine/esi/4wk"]:
        errors.append("Production graph includes unexpected or missing collections")
    if bands != [
        "ESI_4wk_mean", "ESI_4wk_min", "ESI_4wk_max",
        "FPAR_Aqua_mean", "FPAR_Aqua_min", "FPAR_Aqua_max",
    ]:
        errors.append("Production graph includes unexpected or missing output bands")
    qc_masks = [call for call in calls if call["functionName"] == "Image.and"]
    accepted = []
    if len(qc_masks) != 1:
        errors.append("Expected one combined Aqua sensor/SCF QC mask")
    else:
        mask = {"functionInvocationValue": qc_masks[0]}
        accepted = [qc for qc in range(256) if evaluate(mask, qc)]
        expected = [qc for qc in range(256) if qc % 4 in (2, 3) and not 128 <= qc <= 159]
        if accepted != expected:
            errors.append("Production QC expression differs from the historical Aqua rule")
    return {
        "mode": "channel-graph-check", "status": "fail" if errors else "pass",
        "datasets": datasets, "bands": bands, "errors": errors,
        "qc_bytes_checked": 256 if len(qc_masks) == 1 else 0,
        "qc_bytes_accepted": len(accepted),
        "earthengine_api_version": ee.__version__,
        "limitation": "Offline SDK graph construction and QC evaluation only; "
                      "no remote pixels or asset availability checked.",
    }
