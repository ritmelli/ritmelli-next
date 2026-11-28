from collections.abc import Sequence
from pathlib import Path

import pytest

from ritmelli.machine import tasks

# The files v0.7.0 hands to schtasks, made by its own create_task.
V070 = Path(__file__).with_name("fixtures") / "v0.7.0"
EXE = r"C:\Program Files\Ritmelli\ritmelli.exe"
UPDATE = tasks.UPDATE_TASK
MIC = tasks.MIC_TASK


@pytest.fixture
def schtasks(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Each schtasks call, in order. Deleting the update task runs past its time, and
    the update task is still there."""
    calls: list[list[str]] = []

    def run(argv: Sequence[str], timeout: float) -> tuple[int, str]:
        calls.append(list(argv[1:]))
        if argv[1] == "/delete" and argv[3] == UPDATE:
            raise TimeoutError("schtasks ran past 30 s")
        return (0 if argv[1] == "/query" and argv[3] == UPDATE else 1), ""

    monkeypatch.setattr(tasks, "system32", str)
    monkeypatch.setattr(tasks, "run", run)
    return calls


def test_both_task_files_are_the_ones_of_v0_7_0() -> None:
    update = tasks.definition(tasks.UPDATE_XML, EXE)
    assert update == (V070 / "update-task.xml").read_bytes()
    assert tasks.definition(tasks.MIC_XML, EXE) == (V070 / "mic-task.xml").read_bytes()


def test_the_mic_task_ends_and_removes_the_update_task_first(
    schtasks: list[list[str]],
) -> None:
    assert tasks.disarm(MIC) == [
        "Ritmelli Atualiza: schtasks ran past 30 s",
        "the task Ritmelli Atualiza is still there",
    ]
    assert schtasks == [
        ["/end", "/tn", UPDATE],
        ["/delete", "/tn", UPDATE, "/f"],
        ["/delete", "/tn", MIC, "/f"],
        ["/query", "/tn", UPDATE],
        ["/query", "/tn", MIC],
    ]


def test_the_update_round_ends_no_task(schtasks: list[list[str]]) -> None:
    assert len(tasks.disarm(UPDATE)) == 2
    assert [call[:3] for call in schtasks] == [
        ["/delete", "/tn", MIC],
        ["/delete", "/tn", UPDATE],
        ["/query", "/tn", MIC],
        ["/query", "/tn", UPDATE],
    ]
