"""Build a deterministic code-only ZIP from the replication directory.

Only the root ``README.md``, ``requirements.txt``, and Python source files
are eligible. Unknown files are refused so data, credentials, notebooks, caches, and repository
metadata cannot enter the archive through a broad directory copy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections.abc import Sequence
from pathlib import Path


FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
VENDOR_REVISION = "b50430bd9b2b00e1392532202b88ded6c416932a"
IGNORED_DIRECTORIES = {"__pycache__", ".git"}


class ReleaseError(ValueError):
    """Raised when the release tree violates the code-only contract."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contains_secret(text: str) -> str | None:
    patterns = (
        ("private key", re.compile("-----BEGIN " "(?:RSA |EC )?PRIVATE KEY-----")),
        ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
        ("OpenAI-style key", re.compile(r"sk-[0-9A-Za-z]{20,}")),
        (
            "assigned API token",
            re.compile(
                r"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*=\s*['\"][^'\"]{12,}['\"]"
            ),
        ),
    )
    for label, pattern in patterns:
        if pattern.search(text):
            return label
    return None


def collect_release_files(source: Path) -> list[Path]:
    """Return validated, sorted files relative to ``source``."""

    source = source.resolve()
    readme = source / "README.md"
    if not readme.is_file():
        raise ReleaseError(f"required release README is missing: {readme}")
    requirements = source / "requirements.txt"
    if not requirements.is_file():
        raise ReleaseError(f"required release requirements are missing: {requirements}")

    allowed: list[Path] = []
    unexpected: list[Path] = []
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        if path.is_symlink():
            unexpected.append(relative)
        elif path.is_file() and (
            relative in (Path("README.md"), Path("requirements.txt")) or path.suffix == ".py"
        ):
            allowed.append(relative)
        elif path.is_file():
            unexpected.append(relative)
    if unexpected:
        names = ", ".join(path.as_posix() for path in sorted(unexpected))
        raise ReleaseError(f"unexpected files in code-only release tree: {names}")

    readme_text = readme.read_text(encoding="utf-8")
    missing_notices = [
        marker
        for marker in ("gee_s1_ard", "MIT", VENDOR_REVISION)
        if marker not in readme_text
    ]
    if missing_notices:
        raise ReleaseError(
            "README is missing vendor attribution markers: " + ", ".join(missing_notices)
        )

    vendor_files = [
        relative
        for relative in allowed
        if relative.parts[:2] == ("vendor", "gee_s1_ard") and relative.suffix == ".py"
    ]
    if not vendor_files:
        raise ReleaseError("no vendored gee_s1_ard Python files were found")
    for relative in vendor_files:
        text = (source / relative).read_text(encoding="utf-8")
        if "MIT License" not in text or VENDOR_REVISION not in text:
            raise ReleaseError(
                f"vendored source lacks the MIT notice or revision header: {relative.as_posix()}"
            )

    for relative in allowed:
        data = (source / relative).read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ReleaseError(f"release text is not UTF-8: {relative.as_posix()}") from exc
        secret = _contains_secret(text)
        if secret:
            raise ReleaseError(f"possible {secret} in {relative.as_posix()}")
    return sorted(allowed, key=lambda item: item.as_posix())


def build_release(source: Path, output: Path) -> dict[str, object]:
    """Write a deterministic ZIP and return its hashes and member list."""

    source = source.resolve()
    output = output.resolve()
    try:
        output.relative_to(source)
    except ValueError:
        pass
    else:
        raise ReleaseError("archive output must be outside the replication source tree")
    if output.exists() and not output.is_file():
        raise ReleaseError(f"archive output is not a regular file: {output}")

    files = collect_release_files(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    if temporary.exists():
        raise ReleaseError(f"temporary archive path already exists: {temporary}")

    members: list[dict[str, object]] = []
    try:
        with zipfile.ZipFile(
            temporary,
            mode="x",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative in files:
                data = (source / relative).read_bytes()
                archive_path = (Path(source.name) / relative).as_posix()
                info = zipfile.ZipInfo(archive_path, date_time=FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.flag_bits |= 0x800
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
                members.append(
                    {"path": archive_path, "bytes": len(data), "sha256": _sha256(data)}
                )
        with zipfile.ZipFile(temporary, "r") as archive:
            bad_member = archive.testzip()
            names = archive.namelist()
        if bad_member is not None:
            raise ReleaseError(f"ZIP integrity check failed at {bad_member}")
        expected_names = [item["path"] for item in members]
        if names != expected_names:
            raise ReleaseError("ZIP member order/content differs from the explicit release list")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "archive": str(output),
        "archive_bytes": output.stat().st_size,
        "archive_sha256": _sha256(output.read_bytes()),
        "deterministic_timestamp": "1980-01-01T00:00:00",
        "member_count": len(members),
        "members": members,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="ZIP path outside replication/")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_release(Path(__file__).resolve().parent, args.output)
    except (OSError, ReleaseError, zipfile.BadZipFile) as exc:
        print(f"release build failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
