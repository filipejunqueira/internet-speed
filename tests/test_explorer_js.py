"""The explorer's JavaScript tests, run through pytest so one command gates the whole project.

The modules under `src/pingme/site/` are plain ES modules with no build step, so node's
own test runner reads `tests/js/` directly. Without node there is nothing to run and the
test says so instead of failing: node is not a dependency of the Python package.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_explorer_javascript():
    if shutil.which("node") is None:
        pytest.skip("node is not installed, so the explorer's JavaScript tests cannot run")
    # node exits 0 when the pattern below matches nothing, so an empty directory would
    # look like a clean run. Check first: no test files is a broken checkout, not a pass.
    if not sorted((ROOT / "tests" / "js").glob("*.test.js")):
        pytest.fail("tests/js holds no *.test.js files, so no JavaScript was tested",
                    pytrace=False)
    # node 26 does not walk a bare directory here: it tries to load "tests/js" as a module
    # and fails. Given a pattern it expands the glob itself, which is why one is passed.
    #
    # Run under two extreme clocks as well as this machine's own. The page is read wherever
    # the reader happens to be, and a stamp with no offset means UTC to Python but local
    # time to `new Date`, so a run's route could carry one date on the report page and
    # another in the explorer. Two of the cases in tests/fixtures/trace-note-cases.json sit
    # either side of midnight UTC for exactly this: under a clock ahead of UTC one of them
    # crosses back a day, under a clock behind it the other crosses forward. Neither bites
    # unless the suite actually runs somewhere that is not UTC, which is what these are.
    for zone in (None, "Pacific/Kiritimati", "Pacific/Midway"):  # here, UTC+14, UTC-11
        env = None if zone is None else {**os.environ, "TZ": zone}
        done = subprocess.run(["node", "--test", "tests/js/*.test.js"], cwd=ROOT, env=env,
                              capture_output=True, text=True)
        if done.returncode != 0:
            where = "this machine's own clock" if zone is None else f"TZ={zone}"
            pytest.fail(f"under {where}:\n" + done.stdout + done.stderr, pytrace=False)
