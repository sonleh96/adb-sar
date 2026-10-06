"""Run offline method checks and bounded validation of extraction CSV samples.

This tool does not contact Earth Engine and does not claim that inspected
values came from a particular upstream product. Reference comparisons require
an independently supplied reference, explicit key columns, and explicit
tolerances for every column that may differ numerically.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import subprocess
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path

from .common import month_windows
from .extract_channels import fpar_qc_accepts
from .extract_covariates import relative_humidity_fraction
from .extract_fire import fire_pixel_is_valid, frp_min_reducer, scale_frp
from .extract_rvi import rvi_value


EXPECTED_HANDOFF_COLUMNS = (
    "year",
    "mon",
    "lon",
    "lat",
    "ndvi",
    "rvi",
    "pm25_mean",
    "temp_av",
    "hum_av",
    "luminosity",
)
HANDOFF_NUMERIC_COLUMNS = EXPECTED_HANDOFF_COLUMNS
MAX_REPORTED_ERRORS = 100
LIMITATION = (
    "This is a bounded offline schema, method, or supplied-reference check. "
    "It does not establish full-dataset coverage, extraction provenance, "
    "remote asset availability, or reproduction of downstream analysis."
)


class ValidationError(ValueError):
    """Raised for invalid validation requests or structurally invalid CSVs."""


class OfflineMethodTests(unittest.TestCase):
    def test_historical_and_full_month_leap_boundaries(self) -> None:
        self.assertEqual(
            month_windows("2020-02", "2020-02", "historical"),
            (("2020-02", "2020-02-01", "2020-02-29"),),
        )
        self.assertEqual(
            month_windows("2020-02", "2020-02", "full-month"),
            (("2020-02", "2020-02-01", "2020-03-01"),),
        )
        self.assertEqual(
            month_windows("2020-12", "2020-12", "full-month"),
            (("2020-12", "2020-12-01", "2021-01-01"),),
        )

    def test_relative_humidity_is_fraction(self) -> None:
        self.assertEqual(relative_humidity_fraction(20.0, 20.0), 1.0)
        self.assertAlmostEqual(relative_humidity_fraction(30.0, 20.0), 0.550774901, places=8)

    def test_rvi_uses_linear_ratio(self) -> None:
        self.assertAlmostEqual(rvi_value(0.08, 0.02), 0.8)
        with self.assertRaises(ZeroDivisionError):
            rvi_value(0.0, 0.0)

    def test_fire_mask_low_bits(self) -> None:
        self.assertTrue(fire_pixel_is_valid(7, 0))
        self.assertTrue(fire_pixel_is_valid(0b1_0111, 0b100_0010))
        self.assertFalse(fire_pixel_is_valid(6, 0))
        self.assertFalse(fire_pixel_is_valid(7, 3))

    def test_frp_scale_and_historical_min_alias(self) -> None:
        self.assertAlmostEqual(scale_frp(123), 12.3)
        self.assertEqual(frp_min_reducer("historical"), "max")
        self.assertEqual(frp_min_reducer("corrected"), "min")

    def test_fpar_qc_retains_only_aqua_and_excludes_not_produced(self) -> None:
        self.assertTrue(fpar_qc_accepts(2))
        self.assertFalse(fpar_qc_accepts(0))
        self.assertFalse(fpar_qc_accepts(130))
        self.assertTrue(fpar_qc_accepts(98))
        self.assertTrue(fpar_qc_accepts(31))

    def test_channels_cli_plans_only_requested_products(self) -> None:
        result = subprocess.run(
            [
                sys.executable, "-m", "replication.extract_channels",
                "--start-month", "2020-02", "--end-month", "2020-03",
                "--tile-id", "N10E105_0_1", "--dry-run",
            ],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        plan = json.loads(result.stdout)
        self.assertEqual(plan["task_count"], 2)
        self.assertEqual(plan["datasets"], [
            "projects/climate-engine/esi/4wk", "MODIS/061/MCD15A3H",
        ])
        self.assertEqual(plan["output_bands"], [
            "ESI_4wk_mean", "ESI_4wk_min", "ESI_4wk_max",
            "FPAR_Aqua_mean", "FPAR_Aqua_min", "FPAR_Aqua_max",
        ])
        self.assertEqual(plan["month_windows"][0], {
            "month": "2020-02", "start": "2020-02-01", "exclusive_end": "2020-02-29",
        })


def run_self_test() -> dict[str, object]:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(OfflineMethodTests)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    return {
        "mode": "self-test",
        "status": "pass" if result.wasSuccessful() else "fail",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "details": output.getvalue().splitlines(),
        "limitation": LIMITATION,
    }


def _add_error(errors: list[str], message: str) -> None:
    if len(errors) < MAX_REPORTED_ERRORS:
        errors.append(message)


def _read_header(reader: csv.reader, path: Path) -> list[str]:
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValidationError(f"empty CSV: {path}") from exc
    if not header or any(name == "" for name in header):
        raise ValidationError(f"blank column name in {path}")
    if len(header) != len(set(header)):
        raise ValidationError(f"duplicate column names in {path}")
    return header


def inspect_handoff_csv(path: Path, row_limit: int) -> dict[str, object]:
    """Inspect only the first ``row_limit`` records of a candidate handoff."""

    if row_limit <= 0:
        raise ValidationError("row limit must be positive")
    errors: list[str] = []
    null_counts = {name: 0 for name in EXPECTED_HANDOFF_COLUMNS}
    duplicate_count = 0
    keys: set[tuple[str, str, str, str]] = set()
    rows_read = 0
    truncated = False
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = _read_header(reader, path)
        missing = [name for name in EXPECTED_HANDOFF_COLUMNS if name not in header]
        if missing:
            raise ValidationError("missing expected handoff columns: " + ", ".join(missing))
        indexes = {name: header.index(name) for name in EXPECTED_HANDOFF_COLUMNS}
        for csv_row, row in enumerate(reader, start=2):
            if rows_read >= row_limit:
                truncated = True
                break
            rows_read += 1
            if len(row) != len(header):
                _add_error(
                    errors,
                    f"row {csv_row}: expected {len(header)} fields, found {len(row)}",
                )
                continue
            for name in HANDOFF_NUMERIC_COLUMNS:
                value = row[indexes[name]]
                if value == "":
                    null_counts[name] += 1
                    continue
                try:
                    numeric = float(value)
                except ValueError:
                    _add_error(errors, f"row {csv_row}: {name} is not numeric: {value!r}")
                else:
                    if not math.isfinite(numeric):
                        _add_error(errors, f"row {csv_row}: {name} is not finite: {value!r}")
            key = tuple(row[indexes[name]] for name in ("year", "mon", "lon", "lat"))
            if any(value == "" for value in key):
                _add_error(errors, f"row {csv_row}: null year/mon/lon/lat key")
            elif key in keys:
                duplicate_count += 1
                _add_error(errors, f"row {csv_row}: duplicate sampled key {key!r}")
            else:
                keys.add(key)
    return {
        "mode": "handoff-csv",
        "status": "pass" if not errors else "fail",
        "path": str(path.resolve()),
        "column_count": len(header),
        "rows_inspected": rows_read,
        "row_limit": row_limit,
        "additional_rows_exist": truncated,
        "expected_core_columns": list(EXPECTED_HANDOFF_COLUMNS),
        "null_counts_in_sample": null_counts,
        "duplicate_keys_in_sample": duplicate_count,
        "errors": errors,
        "errors_truncated": len(errors) >= MAX_REPORTED_ERRORS,
        "limitation": LIMITATION,
    }


def _read_keyed_sample(
    path: Path,
    keys: Sequence[str],
    row_limit: int,
) -> tuple[list[str], dict[tuple[str, ...], list[str]], list[str], bool]:
    errors: list[str] = []
    records: dict[tuple[str, ...], list[str]] = {}
    truncated = False
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = _read_header(reader, path)
        missing = [name for name in keys if name not in header]
        if missing:
            raise ValidationError(f"key columns missing from {path}: {', '.join(missing)}")
        indexes = tuple(header.index(name) for name in keys)
        for offset, row in enumerate(reader):
            csv_row = offset + 2
            if offset >= row_limit:
                truncated = True
                break
            if len(row) != len(header):
                _add_error(
                    errors,
                    f"{path} row {csv_row}: expected {len(header)} fields, found {len(row)}",
                )
                continue
            key = tuple(row[index] for index in indexes)
            if any(value == "" for value in key):
                _add_error(errors, f"{path} row {csv_row}: null comparison key {key!r}")
            elif key in records:
                _add_error(errors, f"{path} row {csv_row}: duplicate comparison key {key!r}")
            else:
                records[key] = row
    return header, records, errors, truncated


def compare_csv_samples(
    reference: Path,
    candidate: Path,
    *,
    keys: Sequence[str],
    tolerances: dict[str, float],
    row_limit: int,
) -> dict[str, object]:
    """Compare bounded keyed samples from independent CSV files."""

    if not keys:
        raise ValidationError("at least one explicit --key is required")
    if len(keys) != len(set(keys)):
        raise ValidationError("comparison keys must be unique")
    if row_limit <= 0:
        raise ValidationError("row limit must be positive")

    ref_header, ref_rows, errors, ref_truncated = _read_keyed_sample(reference, keys, row_limit)
    cand_header, cand_rows, candidate_errors, cand_truncated = _read_keyed_sample(
        candidate, keys, row_limit
    )
    errors.extend(candidate_errors)
    if cand_header != ref_header:
        _add_error(errors, "candidate header does not exactly match reference columns and order")
    missing_tolerances = [name for name in tolerances if name not in ref_header]
    if missing_tolerances:
        raise ValidationError(
            "tolerance columns missing from reference: " + ", ".join(missing_tolerances)
        )

    compared = 0
    for key in sorted(ref_rows.keys() | cand_rows.keys()):
        if key not in cand_rows:
            _add_error(errors, f"key missing from candidate: {key!r}")
            continue
        if key not in ref_rows:
            _add_error(errors, f"extra key in candidate: {key!r}")
            continue
        if cand_header != ref_header:
            continue
        compared += 1
        ref_row = ref_rows[key]
        cand_row = cand_rows[key]
        for index, name in enumerate(ref_header):
            if name in keys:
                continue
            reference_value = ref_row[index]
            candidate_value = cand_row[index]
            if name not in tolerances:
                if candidate_value != reference_value:
                    _add_error(
                        errors,
                        f"key {key!r}, {name}: {candidate_value!r} != {reference_value!r}",
                    )
                continue
            if reference_value == "" or candidate_value == "":
                if candidate_value != reference_value:
                    _add_error(
                        errors,
                        f"key {key!r}, {name}: null mismatch {candidate_value!r} vs {reference_value!r}",
                    )
                continue
            try:
                reference_number = float(reference_value)
                candidate_number = float(candidate_value)
            except ValueError:
                _add_error(errors, f"key {key!r}, {name}: tolerance requires numeric values")
                continue
            if not (math.isfinite(reference_number) and math.isfinite(candidate_number)):
                _add_error(errors, f"key {key!r}, {name}: non-finite numeric value")
            elif abs(candidate_number - reference_number) > tolerances[name]:
                _add_error(
                    errors,
                    f"key {key!r}, {name}: absolute difference "
                    f"{abs(candidate_number - reference_number):.12g} exceeds {tolerances[name]:.12g}",
                )

    return {
        "mode": "reference-comparison",
        "status": "pass" if not errors else "fail",
        "reference": str(reference.resolve()),
        "candidate": str(candidate.resolve()),
        "keys": list(keys),
        "tolerances": tolerances,
        "row_limit_per_file": row_limit,
        "reference_rows_loaded": len(ref_rows),
        "candidate_rows_loaded": len(cand_rows),
        "matching_keys_compared": compared,
        "reference_has_additional_rows": ref_truncated,
        "candidate_has_additional_rows": cand_truncated,
        "errors": errors,
        "errors_truncated": len(errors) >= MAX_REPORTED_ERRORS,
        "limitation": LIMITATION,
    }


def compare_frp_json_archive(
    json_directory: Path,
    csv_path: Path,
    *,
    row_limit: int,
    tolerance: float,
) -> dict[str, object]:
    """Compare a bounded prefix of an archived FRP CSV to its source JSON files."""

    if row_limit <= 0:
        raise ValidationError("row limit must be positive")
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValidationError("FRP tolerance must be finite and non-negative")
    if not json_directory.is_dir():
        raise ValidationError(f"FRP JSON directory does not exist: {json_directory}")

    errors: list[str] = []
    rows_compared = 0
    truncated = False
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        header = _read_header(reader, csv_path)
        for required in ("GID", "date"):
            if required not in header:
                raise ValidationError(f"FRP CSV is missing required column {required}")
        gid_index = header.index("GID")
        date_index = header.index("date")
        for offset, row in enumerate(reader):
            csv_row = offset + 2
            if offset >= row_limit:
                truncated = True
                break
            if len(row) != len(header):
                _add_error(errors, f"FRP CSV row {csv_row} has the wrong field count")
                continue
            gid = row[gid_index]
            date = row[date_index]
            if not re.fullmatch(r"[A-Za-z0-9._-]+", gid) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}", date
            ):
                _add_error(errors, f"FRP CSV row {csv_row} has an unsafe or invalid GID/date")
                continue
            source = json_directory / f"{gid}_{date[:7]}.json"
            try:
                payload = json.loads(source.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                _add_error(errors, f"FRP CSV row {csv_row}: cannot read {source.name}: {exc}")
                continue
            if not isinstance(payload, dict):
                _add_error(errors, f"FRP source is not a JSON object: {source.name}")
                continue
            if set(payload) != set(header):
                _add_error(errors, f"FRP source schema differs from CSV header: {source.name}")
                continue
            rows_compared += 1
            for index, name in enumerate(header):
                expected = payload[name]
                actual = row[index]
                if expected is None:
                    if actual != "":
                        _add_error(errors, f"{source.name}, {name}: expected null, found {actual!r}")
                elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
                    try:
                        actual_number = float(actual)
                    except ValueError:
                        _add_error(errors, f"{source.name}, {name}: expected numeric value")
                    else:
                        expected_number = float(expected)
                        if not (math.isfinite(expected_number) and math.isfinite(actual_number)):
                            _add_error(errors, f"{source.name}, {name}: non-finite numeric value")
                        elif abs(actual_number - expected_number) > tolerance:
                            _add_error(
                                errors,
                                f"{source.name}, {name}: difference "
                                f"{abs(actual_number - expected_number):.12g} exceeds {tolerance:.12g}",
                            )
                elif actual != str(expected):
                    _add_error(
                        errors,
                        f"{source.name}, {name}: {actual!r} != {str(expected)!r}",
                    )
    return {
        "mode": "archived-frp-json-to-csv",
        "status": "pass" if not errors else "fail",
        "json_directory": str(json_directory.resolve()),
        "csv": str(csv_path.resolve()),
        "rows_compared": rows_compared,
        "row_limit": row_limit,
        "additional_csv_rows_exist": truncated,
        "absolute_numeric_tolerance": tolerance,
        "errors": errors,
        "errors_truncated": len(errors) >= MAX_REPORTED_ERRORS,
        "limitation": LIMITATION,
    }


def _parse_tolerances(values: Sequence[str]) -> dict[str, float]:
    tolerances: dict[str, float] = {}
    for item in values:
        name, separator, raw_value = item.partition("=")
        if not separator or not name:
            raise ValidationError(f"invalid tolerance {item!r}; expected COLUMN=VALUE")
        if name in tolerances:
            raise ValidationError(f"duplicate tolerance for {name}")
        try:
            tolerance = float(raw_value)
        except ValueError as exc:
            raise ValidationError(f"invalid numeric tolerance: {item!r}") from exc
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValidationError(f"tolerance must be finite and non-negative: {item!r}")
        tolerances[name] = tolerance
    return tolerances


def _emit_report(report: dict[str, object], destination: Path | None) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if destination is None:
        print(payload, end="")
        return
    package_root = Path(__file__).resolve().parent
    resolved = destination.resolve()
    try:
        resolved.relative_to(package_root)
    except ValueError:
        pass
    else:
        raise ValidationError("validation reports must be written outside replication/")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(payload, encoding="utf-8")
    print(f"wrote validation report: {resolved}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="run offline formula and date tests")
    mode.add_argument(
        "--channel-graph-check",
        action="store_true",
        help="check the real ESI/Aqua graph offline; requires Earth Engine SDK test metadata",
    )
    mode.add_argument("--csv", type=Path, help="inspect a candidate SAR_SVN_rice_reprod.csv")
    mode.add_argument("--reference", type=Path, help="independent reference CSV for comparison")
    mode.add_argument(
        "--frp-json-dir",
        type=Path,
        help="archived regional FRP JSON directory to compare with --frp-csv",
    )
    parser.add_argument("--candidate", type=Path, help="candidate CSV paired with --reference")
    parser.add_argument("--frp-csv", type=Path, help="archived FRP CSV paired with --frp-json-dir")
    parser.add_argument(
        "--frp-tolerance",
        type=float,
        default=1e-12,
        help="absolute numeric tolerance for archived FRP comparison (default: 1e-12)",
    )
    parser.add_argument("--key", action="append", default=[], help="comparison key; repeatable")
    parser.add_argument(
        "--tolerance",
        action="append",
        default=[],
        metavar="COLUMN=VALUE",
        help="absolute numeric tolerance; unlisted columns require exact text equality",
    )
    parser.add_argument("--rows", type=int, default=1000, help="maximum rows read per CSV (default: 1000)")
    parser.add_argument("--report", type=Path, help="optional JSON report path outside replication/")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.channel_graph_check:
            if args.candidate or args.frp_csv or args.key or args.tolerance:
                raise ValidationError("comparison options cannot be used with --channel-graph-check")
            from .validate_channel_graph import run_channel_graph_check

            report = run_channel_graph_check()
        elif args.self_test:
            if args.candidate or args.frp_csv or args.key or args.tolerance:
                raise ValidationError("comparison options cannot be used with --self-test")
            report = run_self_test()
        elif args.csv:
            if args.candidate or args.frp_csv or args.key or args.tolerance:
                raise ValidationError("comparison options cannot be used with --csv")
            report = inspect_handoff_csv(args.csv, args.rows)
        elif args.frp_json_dir:
            if args.frp_csv is None:
                raise ValidationError("--frp-csv is required with --frp-json-dir")
            if args.candidate or args.key or args.tolerance:
                raise ValidationError("CSV comparison options cannot be used with --frp-json-dir")
            report = compare_frp_json_archive(
                args.frp_json_dir,
                args.frp_csv,
                row_limit=args.rows,
                tolerance=args.frp_tolerance,
            )
        else:
            if args.candidate is None:
                raise ValidationError("--candidate is required with --reference")
            if args.frp_csv:
                raise ValidationError("--frp-csv can only be used with --frp-json-dir")
            report = compare_csv_samples(
                args.reference,
                args.candidate,
                keys=tuple(args.key),
                tolerances=_parse_tolerances(args.tolerance),
                row_limit=args.rows,
            )
        _emit_report(report, args.report)
    except (OSError, csv.Error, ValidationError, RuntimeError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 2
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
