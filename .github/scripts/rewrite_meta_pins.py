"""Rewrite all rgevolve sub-package pins in pyproject.toml to ==VERSION.

Reads VERSION from the environment and modifies pyproject.toml in the
current working directory. Each of the nine sub-package pins must
appear exactly once; the script errors out if any pin is missing or
duplicated. Idempotent: a no-op write if the file is already at the
target version.

Run locally (from the rgevolve meta-repo root):
    VERSION=0.1.2 python3 .github/scripts/rewrite_meta_pins.py
"""

from __future__ import annotations

import os
import re
import sys

SUBPACKAGES = [
    "rgevolve-core",
    "rgevolve.smeft.warsaw",
    "rgevolve.smeft.warsaw_up",
    "rgevolve.wet.flavio",
    "rgevolve.wet.jms",
    "rgevolve.wet_3.flavio",
    "rgevolve.wet_3.jms",
    "rgevolve.wet_4.flavio",
    "rgevolve.wet_4.jms",
]
PYPROJECT_PATH = "pyproject.toml"


def main() -> int:
    version = os.environ["VERSION"]
    with open(PYPROJECT_PATH) as f:
        src = f.read()

    new = src
    for dist in SUBPACKAGES:
        pattern = re.compile(
            r'(?P<prefix>["\']?)'
            + re.escape(dist)
            + r'==(?P<old>[A-Za-z0-9._+\-]+)(?P<suffix>["\']?)'
        )
        matches = list(pattern.finditer(new))
        if not matches:
            print(
                f"::error::no pin found for {dist} in {PYPROJECT_PATH}",
                file=sys.stderr,
            )
            return 1
        if len(matches) > 1:
            print(
                f"::error::multiple pins found for {dist} in {PYPROJECT_PATH}",
                file=sys.stderr,
            )
            return 1
        replacement = r"\g<prefix>" + dist + "==" + version + r"\g<suffix>"
        new = pattern.sub(replacement, new)

    if new == src:
        print("No pin changes (already at the target version). Skipping write.")
    else:
        with open(PYPROJECT_PATH, "w") as f:
            f.write(new)
        print(f"Rewrote pins in {PYPROJECT_PATH} to =={version}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
