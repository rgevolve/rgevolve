"""Verify the requested rgevolve version is a strict next-increment.

Reads VERSION from the environment, fetches the latest final version of
rgevolve from PyPI, and exits 0 if VERSION is a valid next-increment
(patch+1, minor+1 with patch=0, or major+1 with minor=patch=0) and 1
otherwise. Pre-releases (`.dev`, `rc`, `.post`) are matched against
their PEP 440 base version, so `0.1.2.dev0` is a valid next from
`0.1.1`. Skips the check (exit 0 with a message) if rgevolve has no
prior final release on PyPI.

Run locally:
    VERSION=0.1.2 python3 .github/scripts/check_version.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from packaging.version import InvalidVersion, Version

META_DIST = "rgevolve"


def decompose(v: Version) -> tuple[int, int, int]:
    parts = list(v.release) + [0, 0, 0]
    return parts[0], parts[1], parts[2]


def main() -> int:
    new_str = os.environ["VERSION"]
    try:
        new = Version(new_str)
    except InvalidVersion:
        print(f"::error::New version {new_str!r} is not a valid PEP 440 version.")
        return 1

    try:
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{META_DIST}/json", timeout=15
        ) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(
                f"'{META_DIST}' not yet on PyPI. "
                "Skipping increment check (first-ever release)."
            )
            return 0
        raise

    finals: list[Version] = []
    for v_str in data.get("releases", {}).keys():
        try:
            v = Version(v_str)
        except InvalidVersion:
            continue
        if not v.is_prerelease and not v.is_postrelease:
            finals.append(v)
    if not finals:
        print(f"No prior final version of '{META_DIST}' on PyPI. Skipping increment check.")
        return 0

    latest = max(finals)
    new_base = Version(new.base_version)
    print(f"Latest final version on PyPI: {latest}")
    print(f"New version: {new} (base {new_base})")

    if new_base <= latest:
        print(
            f"::error::New version base {new_base} is not greater than "
            f"latest PyPI version {latest}. Refusing to publish."
        )
        return 1

    nM, nm, np_ = decompose(new_base)
    oM, om, op = decompose(latest)

    ok = (
        (nM == oM and nm == om and np_ == op + 1)
        or (nM == oM and nm == om + 1 and np_ == 0)
        or (nM == oM + 1 and nm == 0 and np_ == 0)
    )
    if not ok:
        print(
            f"::error::New version {new_str} (base {new_base}) "
            f"is not a valid increment from {latest}."
        )
        print(
            f"::error::Allowed next-version base: {oM}.{om}.{op + 1} (patch), "
            f"{oM}.{om + 1}.0 (minor), or {oM + 1}.0.0 (major)."
        )
        print(
            "::error::If you legitimately need to skip a version (e.g. after "
            "a botched release), delete the offending tag from "
            "rgevolve/rgevolve temporarily and re-run."
        )
        return 1

    print(f"OK: {new_str} is a valid next increment from {latest}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
