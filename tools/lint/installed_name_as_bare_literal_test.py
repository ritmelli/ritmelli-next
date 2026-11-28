import ast
from pathlib import Path

import installed_name_as_bare_literal as rule
import pytest

UPDATE = '''def update(args: Sequence[str]) -> int:
    """Alone, the round of the update task. The setup runs tarefa, which creates the
    task, and the uninstaller runs remove, which ends and deletes it."""
    action = args[0] if args else None
    if action == "remove":
        tasks.delete(UPDATE_TASK, end=True)
        return 0
    if action not in (None, "tarefa"):
        print(f"unknown mode: {action}")
        return UNKNOWN
'''
SAVE = """def _save(fx: winreg.HKEYType, saved: winreg.HKEYType, off: int) -> None:
    for name in SAVED_SLOTS:
        if (value := _read(fx, name)) is None:
            with contextlib.suppress(OSError):
                winreg.DeleteValue(saved, name)
        else:
            winreg.SetValueEx(saved, name, 0, value[1], value[0])
    winreg.SetValueEx(saved, "_sem_melhorias", 0, winreg.REG_DWORD, 1 if off else 0)
    missing = [name for name in CREATED_SLOTS if _read(fx, name) is None]
    winreg.SetValueEx(saved, "_ausentes", 0, winreg.REG_MULTI_SZ, missing)
"""
CASES = {
    "#26": (
        "src/ritmelli/app.py",
        UPDATE,
        {'"remove"': "UPDATE_ACTIONS[1]", '"tarefa"': "UPDATE_ACTIONS[0]"},
    ),
    "#54": (
        "src/ritmelli/machine/mic_slots.py",
        SAVE,
        {'"_sem_melhorias"': "ENHANCEMENTS_OFF", '"_ausentes"': "MISSING"},
    ),
}
each = pytest.mark.parametrize(("path", "source", "names"), CASES.values(), ids=CASES)


def hits(path: str, source: str) -> list[tuple[int, str]]:
    return rule.check(Path(path), ast.parse(source), source)


@each
def test_it_flags_each_occurrence(
    path: str, source: str, names: dict[str, str]
) -> None:
    found, lines = dict(hits(path, source)), source.splitlines()
    for literal, name in names.items():
        line = next(n for n, text in enumerate(lines, 1) if literal in text)
        assert name in found.pop(line)
    assert found == {}


@each
def test_the_name_passes(path: str, source: str, names: dict[str, str]) -> None:
    for literal, name in names.items():
        source = source.replace(literal, name)
    assert hits(path, source) == []


def test_a_test_file_passes() -> None:
    assert hits("src/ritmelli/app_test.py", UPDATE) == []
