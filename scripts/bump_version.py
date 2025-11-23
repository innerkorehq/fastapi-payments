#!/usr/bin/env python3
"""Utility to bump the project version declared in pyproject.toml."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^(version\s*=\s*")(?P<version>\d+\.\d+\.\d+)("\s*)$', re.MULTILINE)


class VersionError(RuntimeError):
    """Raised when the version in pyproject.toml cannot be processed."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump the project version.")
    parser.add_argument(
        "part",
        choices=("major", "minor", "patch"),
        default="patch",
        nargs="?",
        help="Which part of the semantic version to bump (default: patch).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the new version without updating pyproject.toml.",
    )
    return parser.parse_args()


def get_current_version(text: str) -> Tuple[str, re.Match[str]]:
    match = VERSION_PATTERN.search(text)
    if not match:
        raise VersionError("Could not find a semantic version in pyproject.toml")
    return match.group("version"), match


def bump(version: str, part: str) -> str:
    try:
        major, minor, patch = [int(piece) for piece in version.split(".")]
    except ValueError as exc:
        raise VersionError(f"Invalid semantic version: {version}") from exc

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    return f"{major}.{minor}.{patch}"


def main() -> None:
    args = parse_args()

    if not PYPROJECT_PATH.exists():
        raise VersionError(f"pyproject.toml not found at {PYPROJECT_PATH}")

    text = PYPROJECT_PATH.read_text(encoding="utf-8")
    current_version, match = get_current_version(text)
    new_version = bump(current_version, args.part)

    if args.dry_run:
        print(f"Current version: {current_version}\nNew version: {new_version}")
        return

    updated_text = (
        text[: match.start()] + match.group(1) + new_version + match.group(3) + text[match.end() :]
    )
    PYPROJECT_PATH.write_text(updated_text, encoding="utf-8")
    print(f"Version bumped from {current_version} to {new_version}")


if __name__ == "__main__":
    try:
        main()
    except VersionError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
