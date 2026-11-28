import ast
from pathlib import Path

import pytest
import starred_literal_tuple

STARRED = {
    "#13": """\
FOLDER: tuple[Ace, ...] = (
    *((0, 0, F, TI), (0, 0, M, SY), (0, 0, M, BA), (0, 0, RX, US)),
    *((0, OICI | IO, GA, SY), (0, OICI | IO, GA, CO), (0, IO, 0xA0000000, US)),
)
""",
    "#54": """\
SAVED_SLOTS = (
    *(ASSOCIATION, LFX, GFX, SFX, MFX, EFX, EFX_LIST, MFX_LIST),
    *(SFX_MODES, MFX_MODES, EFX_MODES),
)
""",
}
DIRECT = {
    "#13": """\
FOLDER: tuple[Ace, ...] = (
    (0, 0, F, TI), (0, 0, M, SY), (0, 0, M, BA), (0, 0, RX, US),
    (0, OICI | IO, GA, SY), (0, OICI | IO, GA, CO), (0, IO, 0xA0000000, US),
)
""",
    "#54": """\
SAVED_SLOTS = (
    ASSOCIATION, LFX, GFX, SFX, MFX, EFX, EFX_LIST, MFX_LIST,
    SFX_MODES, MFX_MODES, EFX_MODES,
)
""",
}
LISTS_AND_SETS = """\
A = [*[1, 2], 3]
B = {*{1, 2}, 3}
C = (*[1], *{2})
"""
NOT_LITERAL = """\
OUR_CLSIDS = (FILTER_CLSID, *HOST_CLSIDS)
Y = [*sorted(X), 4]
"""


def flagged(source: str) -> list[int]:
    tree = ast.parse(source)
    found = starred_literal_tuple.check(Path("src/a.py"), tree, source)
    return [line for line, _ in found]


@pytest.mark.parametrize("pr", STARRED)
def test_it_flags_each_occurrence(pr: str) -> None:
    assert flagged(STARRED[pr]) == [1]


def test_it_flags_a_list_or_a_set_starred_in_a_list_or_a_set() -> None:
    assert flagged(LISTS_AND_SETS) == [1, 2, 3]


@pytest.mark.parametrize("pr", DIRECT)
def test_the_items_written_directly_pass(pr: str) -> None:
    assert flagged(DIRECT[pr]) == []


def test_a_starred_name_or_call_passes() -> None:
    assert flagged(NOT_LITERAL) == []
