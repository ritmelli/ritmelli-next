import re
import subprocess
import sys
from pathlib import Path

import pytest

CASES = Path(__file__).resolve().parent / "ruff"
CODES = sorted(path for path in CASES.glob("*") if path.is_dir())


@pytest.mark.parametrize("code", CODES, ids=lambda code: code.name)
def test_ruff_flags_each_occurrence(code: Path) -> None:
    cases = sorted(p.name for p in code.iterdir() if re.fullmatch(r"pr\d+\.py", p.name))
    assert len(cases) >= 2, f"{code.name}: one pr<n>.py per PR, from two PRs or more"
    ruff = [sys.executable, "-m", "ruff", "check", "--ignore-noqa"]
    flags = ["--output-format", "concise", "--select", code.name, *cases]
    result = subprocess.run([*ruff, *flags], cwd=code, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    flagged = {line.split(":")[0] for line in lines if f": {code.name} " in line}
    assert flagged == set(cases), result.stdout + result.stderr
