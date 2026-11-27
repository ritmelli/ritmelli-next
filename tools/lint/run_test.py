from pathlib import Path

import pytest

import run

RULE = """import ast


def check(path, tree, source):
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    return [(c.lineno, "a planted call") for c in calls if ast.unparse(c) == "plant()"]
"""
TEST = "# The occurrences that promoted it: #3 and #5.\n"


def lines(text: str, count: int) -> str:
    return text + "\n" * (count - text.count("\n"))


def plant(root: Path, rule: str, test: str | None) -> Path:
    lint = root / "tools" / "lint"
    lint.mkdir(parents=True)
    (lint / "planted_call.py").write_text(rule, "utf-8")
    if test is not None:
        (lint / "planted_call_test.py").write_text(test, "utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x = 1\nplant()\n", "utf-8")
    return root


def test_a_rule_flags_the_planted_occurrence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run.main(plant(tmp_path, lines(RULE, 60), TEST)) == 1
    assert capsys.readouterr().out == "src/a.py:2: planted-call: a planted call\n"


@pytest.mark.parametrize(
    ("rule", "test", "refusal"),
    [
        (RULE, None, "tools/lint/planted_call.py: no tools/lint/planted_call_test.py"),
        (RULE, "# Only #3, twice: #3.\n", "planted_call_test.py: cites fewer than two"),
        (lines(RULE, 61), TEST, "planted_call.py: 61 lines, over 60"),
        ("import os\n" + RULE, TEST, "planted_call.py: imports os"),
    ],
    ids=["no test", "one PR", "61 lines", "a module from outside"],
)
def test_a_rule_is_refused(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    rule: str,
    test: str | None,
    refusal: str,
) -> None:
    assert run.main(plant(tmp_path, rule, test)) == 1
    out = capsys.readouterr().out
    assert refusal in out
    assert "a planted call" not in out
