#!/usr/bin/env python3
"""Write the VERSION changelog section for a GitHub release."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _paths import REPO_ROOT  # noqa: E402  # pylint: disable=wrong-import-position

LOGGER = logging.getLogger(__name__)


def changelog_section(changelog: str, version: str) -> str:
    """Return the changelog section that starts at ``## [version]``."""
    marker = f"## [{version}]"
    start = changelog.find(marker)
    if start < 0:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    end = changelog.find("\n## [", start + len(marker))
    body = changelog[start:] if end < 0 else changelog[start:end]
    return body.strip() + "\n"


def write_release_notes(
    version_file: Path,
    changelog_file: Path,
    output: Path,
) -> None:
    """Read VERSION and CHANGELOG.md, then write one section to ``output``."""
    version = version_file.read_text(encoding="utf-8").strip()
    changelog = changelog_file.read_text(encoding="utf-8")
    section = changelog_section(changelog, version)
    output.write_text(section, encoding="utf-8")
    LOGGER.info("Wrote %s release notes to %s", version, output)


def main() -> None:
    """Write release-notes.md from the changelog section for VERSION."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version-file",
        type=Path,
        default=REPO_ROOT / "VERSION",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=REPO_ROOT / "CHANGELOG.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "release-notes.md",
    )
    args = parser.parse_args()
    write_release_notes(args.version_file, args.changelog, args.output)


if __name__ == "__main__":
    main()
