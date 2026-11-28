import ast
import re
from pathlib import Path

import no_comments
import pytest

MERGED = {
    "#13": """\
CHANGE_ACL = 0x40000 | 0x80000 | 0x10000000  # WRITE_DAC, WRITE_OWNER, GENERIC_ALL
# Write data, append or create, write EA, delete child, write attributes (enough
# to turn an empty folder into a junction), delete, GENERIC_WRITE and CHANGE_ACL
WRITE = 0x2 | 0x4 | 0x10 | 0x40 | 0x100 | 0x10000 | 0x40000000 | CHANGE_ACL
""",
    "#54": """\
# In Properties, 1 turns the audio enhancements off, and then no effect loads.
NO_ENHANCEMENTS = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
# What the mic setup saves before it puts the filter on. Of the slots it may create,
# the missing ones go in _ausentes, and come off when the original comes back.
""",
}
COMMENT_LINES = {"#13": [1, 2, 3], "#54": [1, 3, 4]}
IN_STRINGS = """\
#!/usr/bin/env python
NAME = "#1"
TAG = f"{x}#"
TEXT = "a\u2028#b"
"""


def flagged(source: str, path: str = "src/a.py") -> list[int]:
    found = no_comments.check(Path(path), ast.parse(source), source)
    return [line for line, _ in found]


@pytest.mark.parametrize("pr", MERGED)
def test_it_flags_each_occurrence(pr: str) -> None:
    assert flagged(MERGED[pr]) == COMMENT_LINES[pr]


@pytest.mark.parametrize("pr", MERGED)
def test_the_same_lines_without_the_comments_pass(pr: str) -> None:
    assert flagged(re.sub(r"(?m)^#.*\n|  #.*$", "", MERGED[pr])) == []


def test_a_hash_in_a_string_a_shebang_or_a_ruff_case_passes() -> None:
    assert flagged(IN_STRINGS) == []
    assert flagged(MERGED["#13"], "tools/lint/ruff/ERA001/pr13.py") == []
