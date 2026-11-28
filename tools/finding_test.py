import json
from pathlib import Path
from typing import Any

import finding
import pytest

ISSUES = "https://github.com/ritmelli/ritmelli-next/issues"


class FakeGh:
    def __init__(self) -> None:
        self.issue: dict[str, Any] = {}
        self.issues: list[dict[str, Any]] = []

    def __call__(self, *args: str) -> str:
        verb, issues = args[:2], self.issues
        issue = issues[int(args[2]) - 1] if args[2].isdigit() else {}
        arg = dict(zip(args[2:], args[3:], strict=False))
        if verb[0] == "api":
            keys = ("number", "title", "state", "url", "labels")
            newest = reversed(issues)
            return "\n".join(json.dumps({key: i[key] for key in keys}) for i in newest)
        if verb == ("issue", "view"):
            return json.dumps(issue)
        if verb == ("issue", "create"):
            number = len(issues) + 1
            self.issue = {"number": number, "state": "open", "comments": []}
            self.issue |= {"title": arg["--title"], "body": arg["--body"]}
            self.issue["labels"] = [arg["--label"]]
            self.issue["url"] = f"{ISSUES}/{number}"
            issues.append(self.issue)
        elif verb == ("issue", "comment"):
            issue["comments"].append({"body": arg["--body"]})
        elif verb == ("issue", "reopen"):
            issue["state"] = "open"
        elif verb == ("issue", "edit") and "--add-label" in arg:
            issue["labels"].append(arg["--add-label"])
        elif verb == ("issue", "edit"):
            issue["labels"].remove(arg["--remove-label"])
        elif verb == ("issue", "close"):
            issue["state"] = "closed"
        return ""


def record(gh: FakeGh, tmp_path: Path, **fields: str | None) -> int:
    output = tmp_path / "ruff.txt"
    output.write_text("src/a.py:3:89: E501 Line too long (91 > 88)\n", "utf-16")
    given = {"name": "long-line", "kind": "rule", "pr": "7", "file": "src/a.py"}
    given |= {"line": "3", "command": "uv run ruff check --select E501", **fields}
    argv = [part for key, v in given.items() if v for part in (f"--{key}", v)]
    return finding.main(["record", *argv, "--output-file", str(output)], gh)


def test_a_new_name_creates_the_issue(tmp_path: Path) -> None:
    gh = FakeGh()
    assert record(gh, tmp_path) == 0
    assert gh.issue["title"] == "finding: long-line"
    assert "<!-- occurrence pr=7 file=src/a.py line=3 kind=rule -->" in gh.issue["body"]
    assert "E501 Line too long" in gh.issue["body"]


def test_the_same_name_in_another_pr_comments_and_promotes(tmp_path: Path) -> None:
    gh = FakeGh()
    record(gh, tmp_path)
    record(gh, tmp_path, pr="8")
    assert "pr=8 " in gh.issue["comments"][0]["body"]
    assert gh.issue["labels"] == ["finding", "promote"]


def test_the_same_pr_twice_counts_once(tmp_path: Path) -> None:
    gh = FakeGh()
    record(gh, tmp_path)
    record(gh, tmp_path)
    assert len(gh.issue["comments"]) == 1
    assert gh.issue["labels"] == ["finding"]


def test_a_closed_issue_reopens_with_rule_missed(tmp_path: Path) -> None:
    gh = FakeGh()
    record(gh, tmp_path)
    record(gh, tmp_path, pr="8")
    gh.issue["state"] = "closed"
    record(gh, tmp_path, pr="9")
    assert gh.issue["state"] == "open"
    assert "pr=9 " in gh.issue["comments"][1]["body"]
    assert gh.issue["labels"] == ["finding", "promote", "rule-missed"]


def test_twin_issues_count_as_one_and_fold_into_the_lowest_number(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh()
    record(gh, tmp_path)
    record(gh, tmp_path, name="long-lines", pr="8")
    gh.issue["title"] = "finding: long-line"  # as if the list had not shown #1 yet
    capsys.readouterr()
    finding.main(["list"], gh)
    assert capsys.readouterr().out == f"long-line  2 PRs  {ISSUES}/1\n"
    record(gh, tmp_path, pr="7")  # the second PR comes only from the twin
    first, twin = gh.issues
    bodies = [comment["body"] for comment in first["comments"]]
    assert "pr=7 " in bodies[0] and twin["body"].endswith(bodies[1])
    assert first["labels"] == ["finding", "promote"]
    assert twin["state"] == "closed" and twin["labels"] == []
    assert twin["comments"] == [{"body": "Duplicate of #1"}]


def test_a_missing_field_or_a_bad_name_exits_with_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = FakeGh()
    bad = {"required: --line": {"line": None}, "--name: 'Long_": {"name": "Long_Line"}}
    for error, fields in bad.items():
        with pytest.raises(SystemExit) as stop:
            record(gh, tmp_path, **fields)
        assert stop.value.code == 2
        assert error in capsys.readouterr().err
    assert not gh.issue
