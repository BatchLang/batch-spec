#!/usr/bin/env python3
"""Generate ANTLR Python parser from grammar/*.g4 into generated/python/."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import GENERATED_DIR  # pylint: disable=wrong-import-position
from _paths import GRAMMAR_DIR  # noqa: E402; pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)

# Maven Central publishes antlr4-4.13.2-complete.jar.sha1 and does not publish
# a .jar.sha256 sidecar (the URL returns 404). The SHA-256 below is the digest
# of that same jar after its published SHA-1 matched.
_ANTLR_VERSION = "4.13.2"
_ANTLR_JAR_URL = (
    "https://repo1.maven.org/maven2/org/antlr/antlr4/"
    f"{_ANTLR_VERSION}/antlr4-{_ANTLR_VERSION}-complete.jar"
)
_ANTLR_JAR_SHA1 = "7df86c341abb175a0f4b76a7845074cc45f82ff8"
_ANTLR_JAR_SHA256 = "eae2dfa119a64327444672aff63e9ec35a20180dc5b8090b7a6ab85125df4d76"

_GRAMMAR_FILES = ("BatchLexer.g4", "BatchParser.g4")
_STAMP_NAME = ".grammar-stamp"
_GENERATED_NAMES = (
    "BatchLexer.py",
    "BatchParser.py",
    "BatchParserVisitor.py",
    "__init__.py",
)


def _grammar_fingerprint() -> str:
    digest = hashlib.sha256()
    for name in _GRAMMAR_FILES:
        content = (GRAMMAR_DIR / name).read_bytes()
        content = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(content)
    return digest.hexdigest()


def _normalize_generated_source(content: bytes) -> bytes:
    """Normalize generated sources for cross-platform drift checks.

    ANTLR embeds the grammar path from its argv into a leading comment. Absolute
    paths differ across machines/CI runners, so reduce those to the basename.
    """
    text = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8")
    lines = text.split("\n")
    if lines and lines[0].startswith("# Generated from ") and " by ANTLR " in lines[0]:
        prefix, _, rest = lines[0].partition("# Generated from ")
        path_part, sep, suffix = rest.rpartition(" by ANTLR ")
        if sep:
            basename = Path(path_part.replace("\\", "/")).name
            lines[0] = f"{prefix}# Generated from {basename} by ANTLR {suffix}"
    return "\n".join(lines).encode("utf-8")


def _file_fingerprint(path: Path) -> str:
    return hashlib.sha256(_normalize_generated_source(path.read_bytes())).hexdigest()


def _jar_is_official(payload: bytes) -> bool:
    """Return whether payload matches the Maven Central ANTLR complete jar."""
    sha1 = hashlib.sha1(payload, usedforsecurity=False).hexdigest()
    sha256 = hashlib.sha256(payload).hexdigest()
    return sha1 == _ANTLR_JAR_SHA1 and sha256 == _ANTLR_JAR_SHA256


def _download_antlr_jar() -> bytes:
    """Download the ANTLR complete jar. The caller must reject a bad digest."""
    request = urllib.request.Request(
        _ANTLR_JAR_URL,
        headers={"User-Agent": "batch-spec-generate-parser"},
    )
    # The URL is the pinned Maven Central jar. The caller rejects bytes that
    # do not match the published SHA-1 and SHA-256 before java runs them.
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
        payload: object = response.read()
    if not isinstance(payload, bytes):
        raise SystemExit("ANTLR download did not return bytes")
    LOGGER.info("Downloaded ANTLR %s jar (%s bytes)", _ANTLR_VERSION, len(payload))
    return payload


def _antlr_cache_path() -> Path:
    """Return the private cache path for the verified ANTLR jar."""
    return (
        Path(tempfile.gettempdir())
        / "batch-spec-antlr-cache"
        / f"antlr4-{_ANTLR_VERSION}-complete.jar"
    )


def _atomic_write(destination: Path, payload: bytes) -> None:
    """Publish payload by rename so readers never see a partial jar."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(
        prefix=f"{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    tmp_path = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, destination)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _private_jar_copy(payload: bytes) -> Path:
    """Return a fresh file containing payload for this process to execute."""
    directory = Path(tempfile.mkdtemp(prefix="batch-spec-antlr-"))
    path = directory / f"antlr4-{_ANTLR_VERSION}-complete.jar"
    path.write_bytes(payload)
    return path


def discard_private_jar(path: Path) -> None:
    """Remove a jar directory created by ``_private_jar_copy``."""
    parent = path.parent
    if (
        parent.name.startswith("batch-spec-antlr-")
        and parent.name != "batch-spec-antlr-cache"
    ):
        shutil.rmtree(parent, ignore_errors=True)


def _official_cached_bytes(destination: Path) -> bytes | None:
    """Return cached bytes only when they match and can be read.

    A missing or unreadable cache is a miss. The caller downloads again.
    """
    try:
        payload = destination.read_bytes()
    except OSError:
        return None
    if _jar_is_official(payload):
        return payload
    return None


def _publish_cache(destination: Path, payload: bytes) -> None:
    """Store a verified jar. A cache that cannot be updated is not fatal."""
    try:
        _atomic_write(destination, payload)
    except OSError as exc:
        LOGGER.warning("Cannot cache ANTLR jar at %s: %s", destination, exc)
        return
    try:
        written = destination.read_bytes()
    except OSError as exc:
        LOGGER.warning("Cannot re-read ANTLR jar at %s: %s", destination, exc)
        return
    if not _jar_is_official(written):
        LOGGER.warning("Cached ANTLR jar at %s failed the digest recheck", destination)
        return
    LOGGER.info("Cached verified ANTLR jar at %s", destination)


def verified_antlr_jar() -> Path:
    """Return a private jar copy whose bytes match Maven Central.

    The shared cache is published with ``os.replace`` after the digest check.
    ``java -jar`` receives a separate file written from those verified bytes,
    so a later replacement of the cache path is not what the JVM runs.
    """
    destination = _antlr_cache_path()
    payload = _official_cached_bytes(destination)
    if payload is None:
        payload = _download_antlr_jar()
        if not _jar_is_official(payload):
            raise SystemExit(
                "Refusing to run ANTLR: downloaded jar does not match the "
                "Maven Central SHA-1/SHA-256 for "
                f"antlr4-{_ANTLR_VERSION}-complete.jar"
            )
        _publish_cache(destination, payload)
    else:
        LOGGER.info("Using cached ANTLR jar at %s", destination)
    return _private_jar_copy(payload)


def _run_antlr(output_dir: Path) -> None:
    # Pass grammar basenames with cwd=GRAMMAR_DIR so ANTLR headers are portable
    # (absolute paths embed machine-specific checkout locations and break --check).
    jar_path = verified_antlr_jar()
    cmd = [
        "java",
        "-jar",
        str(jar_path),
        "-Dlanguage=Python3",
        "-visitor",
        "-no-listener",
        "-o",
        str(output_dir),
        *_GRAMMAR_FILES,
    ]
    LOGGER.info("Running verified ANTLR jar %s", jar_path)
    try:
        _ = subprocess.run(cmd, check=True, cwd=GRAMMAR_DIR)
    finally:
        discard_private_jar(jar_path)


def _write_init(output_dir: Path) -> None:
    (output_dir / "__init__.py").write_text(
        '"""ANTLR-generated batch parser (do not edit by hand)."""\n',
        encoding="utf-8",
    )


def generate_parser() -> None:
    """Replace generated/python with a fresh ANTLR run and a grammar stamp."""
    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    _run_antlr(GENERATED_DIR)
    _write_init(GENERATED_DIR)
    (GENERATED_DIR / _STAMP_NAME).write_text(_grammar_fingerprint(), encoding="utf-8")


def _check_generated() -> None:
    names = list(_GENERATED_NAMES) + [_STAMP_NAME]
    missing = [
        GENERATED_DIR / name for name in names if not (GENERATED_DIR / name).is_file()
    ]
    if missing:
        for path in missing:
            print(f"Missing {path}", file=sys.stderr)
        raise SystemExit(1)
    stamp = (GENERATED_DIR / _STAMP_NAME).read_text(encoding="utf-8").strip()
    if stamp != _grammar_fingerprint():
        print(
            "Generated parser is stale (grammar fingerprint mismatch)",
            file=sys.stderr,
        )
        raise SystemExit(1)

    with tempfile.TemporaryDirectory(prefix="batch-spec-antlr-") as tmp:
        tmp_dir = Path(tmp)
        _run_antlr(tmp_dir)
        _write_init(tmp_dir)
        for name in _GENERATED_NAMES:
            committed = GENERATED_DIR / name
            fresh = tmp_dir / name
            if not fresh.is_file():
                print(f"ANTLR did not produce {name}", file=sys.stderr)
                raise SystemExit(1)
            if _file_fingerprint(committed) != _file_fingerprint(fresh):
                print(
                    f"Generated file drift: {name} does not match fresh ANTLR output",
                    file=sys.stderr,
                )
                raise SystemExit(1)
    print("Generated parser is up to date")


def main() -> None:
    """Generate the parser, or check the committed output when ``--check`` is set."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Generate ANTLR Python parser")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        _check_generated()
        return
    generate_parser()
    print(f"Wrote ANTLR output to {GENERATED_DIR}")


if __name__ == "__main__":
    main()
