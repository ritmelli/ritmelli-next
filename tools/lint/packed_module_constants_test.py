import ast
from pathlib import Path

import packed_module_constants
import pytest

PACKED = {
    "#13": """\
SY, BA, LS, US, CO = "S-1-5-18", "S-1-5-32-544", "S-1-5-19", "S-1-5-32-545", "S-1-3-0"
""",
    "#54": """\
ASSOCIATION, LFX, GFX, SFX = f"{_FX},0", f"{_FX},1", f"{_FX},2", f"{_FX},5"
MFX, EFX, MFX_LIST, EFX_LIST = f"{_FX},6", f"{_FX},7", f"{_FX},14", f"{_FX},15"
SFX_MODES, MFX_MODES, EFX_MODES = f"{_MODES},5", f"{_MODES},6", f"{_MODES},7"
""",
}
ONE_PER_LINE = {
    "#13": """\
SY = "S-1-5-18"
BA = "S-1-5-32-544"
LS = "S-1-5-19"
US = "S-1-5-32-545"
CO = "S-1-3-0"
""",
    "#54": """\
ASSOCIATION = f"{_FX},0"
LFX = f"{_FX},1"
GFX = f"{_FX},2"
SFX = f"{_FX},5"
MFX = f"{_FX},6"
EFX = f"{_FX},7"
MFX_LIST = f"{_FX},14"
EFX_LIST = f"{_FX},15"
SFX_MODES = f"{_MODES},5"
MFX_MODES = f"{_MODES},6"
EFX_MODES = f"{_MODES},7"
""",
}
NOT_PACKED = """\
QUOTIENT, REMAINDER = divmod(7, 2)
FIRST, SECOND = PAIR
FIRST, SECOND, THIRD = *PAIR, 3
PAIR.first, PAIR.second = 1, 2


def swap(a, b):
    a, b = b, a
    return a, b


class Pair:
    a, b = 1, 2
"""


def flagged(source: str) -> list[int]:
    tree = ast.parse(source)
    found = packed_module_constants.check(Path("src/a.py"), tree, source)
    return [line for line, _ in found]


@pytest.mark.parametrize(("pr", "lines"), [("#13", [1]), ("#54", [1, 2, 3])])
def test_it_flags_each_occurrence(pr: str, lines: list[int]) -> None:
    assert flagged(PACKED[pr]) == lines


def test_it_flags_a_list_of_names_too() -> None:
    assert flagged("[A, B] = 1, 2\n") == [1]


@pytest.mark.parametrize("pr", ONE_PER_LINE)
def test_one_constant_per_line_passes(pr: str) -> None:
    assert flagged(ONE_PER_LINE[pr]) == []


def test_the_cases_that_do_not_count_pass() -> None:
    assert flagged(NOT_PACKED) == []
