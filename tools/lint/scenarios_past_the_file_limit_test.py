import ast
from pathlib import Path

import pytest
import scenarios_past_the_file_limit as rule

KEPT = """\
def test_the_first_dll_goes_in_with_the_sound_on(pc, tmp_path): ...
def test_the_same_sources_keep_the_dll_and_the_sound(pc, tmp_path): ...
def test_the_same_dll_stays_and_gets_its_digest(pc, tmp_path): ...
def test_the_remove_forgets_the_digest_and_keeps_the_hosts(pc): ...
"""
REPLACED = """\
def test_new_sources_or_v0_7_0_put_back_stop_the_sound_once(pc, capsys, tmp_path):
    for n, (old, saved, only_service) in enumerate(
        ((b"0.900.1", OTHER, True), (b"0.7.0", DIGEST, False))
    ):
        pc.calls.clear()
        assert filter_dll.place(dll, str(installed.parent))
def test_a_failure_after_the_stop_starts_the_sound_before_it_rises(pc, tmp_path): ...
"""
THIRD = '    "#45": ("src/ritmelli/app.py", UPDATE, {}),\n'
INSTALLED = """\
CASES = {
    "#26": ("src/ritmelli/app.py", UPDATE, {'"remove"': "UPDATE_ACTIONS[1]"}),
    "#54": ("src/ritmelli/machine/mic_slots.py", SAVE, {'"_ausentes"': "MISSING"}),
    "#45": ("src/ritmelli/app.py", UPDATE, {}),
}
each = pytest.mark.parametrize(("path", "source", "names"), CASES.values(), ids=CASES)
@each
def test_it_flags_each_occurrence(path, source, names): ...
@each
def test_the_name_passes(path, source, names): ...
@each
def test_a_test_file_passes(path, source, names): ...
"""
LOOPS = """\
def test_inputs():
    for path in (APP, ROOT, LOG):
        assert check(path)
def test_steps():
    for sid, flags in ((US, OICI), (US, IO), (LS, IO)):
        assert sid
    assert check(APP)
"""
CASES = {
    "#42": (
        "src/ritmelli/machine/filter_dll_test.py",
        KEPT + REPLACED,
        7,
        [KEPT, REPLACED],
    ),
    "#86": (
        "tools/lint/installed_name_as_bare_literal_test.py",
        INSTALLED,
        9,
        [INSTALLED.replace(THIRD, "")],
    ),
}
each = pytest.mark.parametrize(
    ("path", "source", "count", "fixed"), CASES.values(), ids=CASES
)


def hits(path: str, source: str) -> list[tuple[int, str]]:
    return rule.check(Path(path), ast.parse(source), source)


@each
def test_it_flags_each_occurrence(
    path: str, source: str, count: int, fixed: list[str]
) -> None:
    assert hits(path, source) == [(1, rule.MESSAGE.format(count, 6))]


@each
def test_the_file_split_or_cut_passes(
    path: str, source: str, count: int, fixed: list[str]
) -> None:
    assert [hits(path, part) for part in fixed] == [[] for _ in fixed]


def test_a_command_holds_three_and_the_rest_of_its_feature_six() -> None:
    feature = "src/ritmelli/features/deck"
    assert hits(f"{feature}/play_test.py", KEPT) == [(1, rule.MESSAGE.format(4, 3))]
    for name in ("on_end", "state", "tuning", "ops/load"):
        assert hits(f"{feature}/{name}_test.py", KEPT) == []
    assert hits(f"{feature}/play.py", KEPT) == []


def test_a_loop_over_single_inputs_or_before_more_steps_counts_once() -> None:
    assert hits("src/ritmelli/machine/protected_folder_test.py", KEPT + LOOPS) == []
