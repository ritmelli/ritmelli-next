import json
import os
import shutil
from pathlib import Path

import pytest

from ritmelli.update import run_state

STATES = Path(__file__).parent / "fixtures" / "state"


def test_each_state_of_v070_keeps_its_keys_and_types(tmp_path: Path) -> None:
    """The files come from the v0.7.0 round. A write drops erro, as v0.7.0 does."""
    goldens = sorted(STATES.glob("*.json"))
    assert len(goldens) == 5
    for golden in goldens:
        before: dict[str, object] = json.loads(golden.read_bytes())
        kept = {key: value for key, value in before.items() if key != "erro"}
        shutil.copyfile(golden, tmp_path / run_state.NAME)
        run_state.write(tmp_path, {})
        after = run_state.read(tmp_path)
        types = {key: type(value) for key, value in after.items()}
        assert types == {key: type(value) for key, value in kept.items()}, golden
        assert {**after, "quando": ""} == {**kept, "quando": ""}, golden


def test_a_missing_or_broken_state_reads_as_empty(tmp_path: Path) -> None:
    assert run_state.read(tmp_path) == {}
    for text in ("", "{", "[]"):
        (tmp_path / run_state.NAME).write_text(text, encoding="utf-8")
        assert run_state.read(tmp_path) == {}


def test_the_swap_windows_refuses_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replace = os.replace
    refusals = 3

    def busy(source: str, target: Path) -> None:
        nonlocal refusals
        if refusals:
            refusals -= 1
            raise PermissionError(source)
        replace(source, target)

    monkeypatch.setattr(os, "replace", busy)
    waits: list[float] = []
    run_state.write(tmp_path, {"estado": "baixando"}, waits.append)
    assert run_state.read(tmp_path)["estado"] == "baixando"
    assert waits == pytest.approx([0.05, 0.1, 0.15])

    refusals = run_state.TRIES
    with pytest.raises(PermissionError):
        run_state.write(tmp_path, {"estado": "pronta"}, waits.append)
    assert run_state.read(tmp_path)["estado"] == "baixando"
    assert [path.name for path in tmp_path.iterdir()] == [run_state.NAME]
