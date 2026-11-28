from pathlib import Path

import finding
import pytest
from finding_test import ISSUES, FakeGh, record


def test_no_issue_prints_no_findings_yet(capsys: pytest.CaptureFixture[str]) -> None:
    assert finding.main(["list"], FakeGh()) == 0
    assert capsys.readouterr().out == "no findings yet\n"


def test_two_findings_print_their_prs_with_promote_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh()
    record(gh, tmp_path, name="dead-branch")
    for pr in ("7", "8", "8"):
        record(gh, tmp_path, pr=pr)
    capsys.readouterr()
    assert finding.main(["list"], gh) == 0
    assert capsys.readouterr().out == (
        f"long-line  2 PRs  promote  {ISSUES}/2\ndead-branch  1 PR  {ISSUES}/1\n"
    )
