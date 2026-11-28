import ast
from pathlib import Path

import constant_with_no_reader as rule
import pytest

OCCURRENCES = {
    "#54": (
        "src/ritmelli/machine/installed.py",
        27,
        'APO_KEY = r"SOFTWARE\\Classes\\AudioEngine\\AudioProcessingObjects"\n',
    ),
    "#85": (
        "src/ritmelli/machine/mic_check.py",
        40,
        "def device_of(name: str) -> str:\n    return name\n",
    ),
}
LATER_READERS = {
    "#54": (
        "src/ritmelli/machine/mic_slots_test.py",
        "from ritmelli.machine.installed import ANY_NODE, APO_KEY, ASSOCIATION, CAPTURE_KEY\n",
    ),
    "#85": (
        "src/ritmelli/machine/mic_setup.py",
        (
            "from ritmelli.machine import mic_check\n"
            "devices = dict.fromkeys(map(mic_check.device_of, report.silent))\n"
        ),
    ),
}
NOT_READERS = {
    "src/ritmelli/audio/capture_test.py": (
        "def test_levels(installed, mic_check):\n"
        "    return installed.APO_KEY, mic_check.device_of\n"
    ),
    "tools/lint/ruff/I001/pr68.py": LATER_READERS["#54"][1],
}
NOT_CHECKED = {
    "src/ritmelli/limit_test.py": """\
LIMIT = 3
Target = tuple[int, str]


def test_the_limit() -> None:
    assert LIMIT == 3
""",
    "tools/lint/ruff/ERA001/pr31.py": "def stop(grace: float) -> float:\n    return grace\n",
}


def flagged(root: Path, files: dict[str, str]) -> list[str]:
    for where, text in files.items():
        (root / where).parent.mkdir(parents=True, exist_ok=True)
        (root / where).write_text(text, "utf-8")
    read = rule.read_elsewhere(root)
    return [
        f"{where}:{line}"
        for where, text in files.items()
        for line, _ in rule.check(Path(where), ast.parse(text), text, read)
    ]


@pytest.mark.parametrize("pr", OCCURRENCES)
def test_it_flags_each_occurrence(pr: str, tmp_path: Path) -> None:
    where, line, text = OCCURRENCES[pr]
    files = {where: "\n" * (line - 1) + text, **NOT_READERS}
    assert flagged(tmp_path, files) == [f"{where}:{line}"]


@pytest.mark.parametrize("pr", LATER_READERS)
def test_the_reader_a_later_commit_added_passes(pr: str, tmp_path: Path) -> None:
    where, _, text = OCCURRENCES[pr]
    reader, read = LATER_READERS[pr]
    assert flagged(tmp_path, {where: text, reader: read}) == []


def test_a_read_in_the_same_file_and_what_it_skips_pass(tmp_path: Path) -> None:
    assert flagged(tmp_path, NOT_CHECKED) == []


def test_an_annotated_constant_is_a_constant_too(tmp_path: Path) -> None:
    files = {"src/ritmelli/slots.py": "SLOTS: tuple[str, ...] = ()\n"}
    assert flagged(tmp_path, files) == ["src/ritmelli/slots.py:1"]
