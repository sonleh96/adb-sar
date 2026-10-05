"""Stream extraction CSV batches or regional JSON records into one CSV.

The command never loads a complete input into memory. It requires identical
ordered headers, preserves every parsed field value, and can check duplicate
``Timestamp``/``lon``/``lat`` keys either in a bounded sample or across the
whole assembly with a temporary SQLite index. ``--json-records`` converts the
fire workflow's one-object-per-region-month files without analysis joins.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path


DEFAULT_KEYS = ("Timestamp", "lon", "lat")


class AssemblyError(ValueError):
    """Raised when input batches cannot be assembled safely."""


def _validate_output_path(output: Path) -> Path:
    resolved = output.resolve()
    package_root = Path(__file__).resolve().parent
    try:
        resolved.relative_to(package_root)
    except ValueError:
        return resolved
    raise AssemblyError("generated CSV output must be outside replication/")


def _expand_inputs(patterns: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = sorted(Path(item) for item in glob.glob(pattern))
        if not matches and Path(pattern).is_file():
            matches = [Path(pattern)]
        if not matches:
            raise AssemblyError(f"input did not match a file: {pattern}")
        for path in matches:
            resolved = path.resolve()
            if not path.is_file():
                raise AssemblyError(f"input is not a file: {path}")
            if resolved not in seen:
                seen.add(resolved)
                paths.append(path)
    if not paths:
        raise AssemblyError("at least one input CSV is required")
    return paths


class _DuplicateChecker:
    def __init__(self, mode: str, limit: int, directory: Path) -> None:
        self.mode = mode
        self.limit = limit
        self.checked = 0
        self._sample: set[tuple[str, ...]] = set()
        self._db_path: Path | None = None
        self._connection: sqlite3.Connection | None = None
        if mode == "sqlite":
            handle = tempfile.NamedTemporaryFile(
                prefix=".sar-keys-",
                suffix=".sqlite3",
                dir=directory,
                delete=False,
            )
            handle.close()
            self._db_path = Path(handle.name)
            self._connection = sqlite3.connect(handle.name)
            self._connection.execute("PRAGMA journal_mode=OFF")
            self._connection.execute("PRAGMA synchronous=OFF")
            self._connection.execute("CREATE TABLE seen (key TEXT PRIMARY KEY) WITHOUT ROWID")

    def add(self, key: tuple[str, ...], *, source: Path, row_number: int) -> None:
        if any(value == "" for value in key):
            raise AssemblyError(
                f"null duplicate-check key in {source} at CSV row {row_number}: {key!r}"
            )
        if self.mode == "none":
            return
        if self.mode == "sample":
            if self.checked >= self.limit:
                return
            if key in self._sample:
                raise AssemblyError(
                    f"duplicate key in checked sample at {source} row {row_number}: {key!r}"
                )
            self._sample.add(key)
            self.checked += 1
            return

        assert self._connection is not None
        encoded = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
        try:
            self._connection.execute("INSERT INTO seen VALUES (?)", (encoded,))
        except sqlite3.IntegrityError as exc:
            raise AssemblyError(
                f"duplicate key in full check at {source} row {row_number}: {key!r}"
            ) from exc
        self.checked += 1
        if self.checked % 100_000 == 0:
            self._connection.commit()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
        if self._db_path is not None:
            self._db_path.unlink(missing_ok=True)


def assemble(
    inputs: Sequence[Path],
    output: Path,
    *,
    duplicate_check: str = "sample",
    sample_key_limit: int = 100_000,
    key_columns: Sequence[str] = DEFAULT_KEYS,
) -> dict[str, object]:
    """Assemble ``inputs`` atomically and return a machine-readable summary."""

    if duplicate_check not in {"none", "sample", "sqlite"}:
        raise AssemblyError("duplicate_check must be none, sample, or sqlite")
    if sample_key_limit <= 0:
        raise AssemblyError("sample_key_limit must be positive")
    if not key_columns and duplicate_check != "none":
        raise AssemblyError("at least one key column is required for duplicate checking")

    output = _validate_output_path(output)
    resolved_inputs = [path.resolve() for path in inputs]
    if output in resolved_inputs:
        raise AssemblyError("output must not overwrite an input CSV")
    output.parent.mkdir(parents=True, exist_ok=True)

    checker = _DuplicateChecker(duplicate_check, sample_key_limit, output.parent)
    temporary: Path | None = None
    expected_header: list[str] | None = None
    key_indexes: tuple[int, ...] = ()
    total_rows = 0
    per_file: dict[str, int] = {}
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as destination:
            temporary = Path(destination.name)
            writer = csv.writer(destination, lineterminator="\n")
            for source in inputs:
                count = 0
                with source.open("r", encoding="utf-8-sig", newline="") as stream:
                    reader = csv.reader(stream)
                    try:
                        header = next(reader)
                    except StopIteration as exc:
                        raise AssemblyError(f"empty CSV: {source}") from exc
                    if not header or any(name == "" for name in header):
                        raise AssemblyError(f"CSV has a blank column name: {source}")
                    if len(header) != len(set(header)):
                        raise AssemblyError(f"CSV has duplicate column names: {source}")
                    if expected_header is None:
                        expected_header = header
                        writer.writerow(header)
                        if duplicate_check != "none":
                            missing = [name for name in key_columns if name not in header]
                            if missing:
                                raise AssemblyError(
                                    "duplicate-check columns missing from header: " + ", ".join(missing)
                                )
                            key_indexes = tuple(header.index(name) for name in key_columns)
                    elif header != expected_header:
                        raise AssemblyError(
                            f"header mismatch in {source}; expected the exact columns and order from {inputs[0]}"
                        )

                    for row_number, row in enumerate(reader, start=2):
                        if len(row) != len(expected_header):
                            raise AssemblyError(
                                f"row width mismatch in {source} at CSV row {row_number}: "
                                f"expected {len(expected_header)}, found {len(row)}"
                            )
                        if duplicate_check != "none":
                            checker.add(
                                tuple(row[index] for index in key_indexes),
                                source=source,
                                row_number=row_number,
                            )
                        writer.writerow(row)
                        count += 1
                        total_rows += 1
                per_file[str(source)] = count
            destination.flush()
            os.fsync(destination.fileno())
        assert temporary is not None
        os.replace(temporary, output)
        temporary = None
    finally:
        checker.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {
        "input_format": "csv",
        "output": str(output),
        "input_count": len(inputs),
        "row_count": total_rows,
        "column_count": len(expected_header or ()),
        "header": expected_header,
        "rows_by_input": per_file,
        "duplicate_check": duplicate_check,
        "duplicate_keys_checked": checker.checked,
        "duplicate_check_complete": duplicate_check == "sqlite",
    }


def _load_json_record(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise AssemblyError(f"invalid JSON record {path}: {exc}") from exc
    if not isinstance(payload, dict) or not payload:
        raise AssemblyError(f"JSON record must be a non-empty object: {path}")
    for name, value in payload.items():
        if not isinstance(name, str) or not name:
            raise AssemblyError(f"JSON record has a blank or non-string field name: {path}")
        if isinstance(value, (dict, list)):
            raise AssemblyError(f"JSON record field {name!r} is nested in {path}")
    return payload


def _csv_scalar(value: object) -> object:
    return "" if value is None else value


def assemble_json_records(
    inputs: Sequence[Path],
    output: Path,
    *,
    duplicate_check: str = "sample",
    sample_key_limit: int = 100_000,
    key_columns: Sequence[str] = ("GID", "date"),
) -> dict[str, object]:
    """Convert flat JSON records to one CSV using a stable union header."""

    if duplicate_check not in {"none", "sample", "sqlite"}:
        raise AssemblyError("duplicate_check must be none, sample, or sqlite")
    if sample_key_limit <= 0:
        raise AssemblyError("sample_key_limit must be positive")

    output = _validate_output_path(output)
    if output in [path.resolve() for path in inputs]:
        raise AssemblyError("output must not overwrite an input record")
    output.parent.mkdir(parents=True, exist_ok=True)

    header: list[str] = []
    seen_columns: set[str] = set()
    for source in inputs:
        record = _load_json_record(source)
        for name in record:
            if name not in seen_columns:
                seen_columns.add(name)
                header.append(name)
    if duplicate_check != "none":
        missing = [name for name in key_columns if name not in seen_columns]
        if missing:
            raise AssemblyError("duplicate-check fields missing from JSON records: " + ", ".join(missing))

    checker = _DuplicateChecker(duplicate_check, sample_key_limit, output.parent)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
            delete=False,
        ) as destination:
            temporary = Path(destination.name)
            writer = csv.writer(destination, lineterminator="\n")
            writer.writerow(header)
            for row_number, source in enumerate(inputs, start=2):
                record = _load_json_record(source)
                if duplicate_check != "none":
                    checker.add(
                        tuple(str(_csv_scalar(record.get(name))) for name in key_columns),
                        source=source,
                        row_number=row_number,
                    )
                writer.writerow([_csv_scalar(record.get(name)) for name in header])
            destination.flush()
            os.fsync(destination.fileno())
        assert temporary is not None
        os.replace(temporary, output)
        temporary = None
    finally:
        checker.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return {
        "input_format": "json-records",
        "output": str(output),
        "input_count": len(inputs),
        "row_count": len(inputs),
        "column_count": len(header),
        "header": header,
        "duplicate_check": duplicate_check,
        "duplicate_keys_checked": checker.checked,
        "duplicate_check_complete": duplicate_check == "sqlite",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="CSV files or shell-style file patterns")
    parser.add_argument("--output", type=Path, required=True, help="assembled CSV path")
    parser.add_argument(
        "--json-records",
        action="store_true",
        help="convert flat one-object-per-record JSON inputs to CSV",
    )
    parser.add_argument(
        "--duplicate-check",
        choices=("sample", "sqlite", "none"),
        default="sample",
        help="sample checks a bounded prefix; sqlite checks every key on disk (default: sample)",
    )
    parser.add_argument(
        "--sample-key-limit",
        type=int,
        default=100_000,
        help="maximum rows checked in sample mode (default: 100000)",
    )
    parser.add_argument(
        "--key",
        action="append",
        dest="keys",
        help="duplicate-key column; repeatable (CSV default: Timestamp,lon,lat; JSON: GID,date)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        inputs = _expand_inputs(args.inputs)
        if args.json_records:
            result = assemble_json_records(
                inputs,
                args.output,
                duplicate_check=args.duplicate_check,
                sample_key_limit=args.sample_key_limit,
                key_columns=tuple(args.keys or ("GID", "date")),
            )
        else:
            result = assemble(
                inputs,
                args.output,
                duplicate_check=args.duplicate_check,
                sample_key_limit=args.sample_key_limit,
                key_columns=tuple(args.keys or DEFAULT_KEYS),
            )
    except (AssemblyError, OSError, csv.Error, sqlite3.Error) as exc:
        print(f"assembly failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
