import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).with_name("mutate.py")
BEFORE = '''"""The planted module."""

NAMES = ("a", "b")


def check(path, items):
    if path in items:
        pass
    return path


LAST = (
    "a",
    "b",
)
'''
AFTER = '''"""The planted module, now with Água."""

NAMES = ("a", "b")
MORE = ["a", "b"]


def check(path, items):
    if path in items and path is not None:
        pass
    with contextlib.suppress(OSError), open(path) as handle:
        handle.read()
    try:
        return path < items >= path
    except OSError:
        return False
    return path


class Box:
    def size(self):
        return [len(self), True]


LAST = (
    "a",
    "【",
)
'''
LISTED = """[[mutant]]
file = "src/pkg/mod.py"
function = "check"
change = "handle.read() -> pass"
why = "listed"

[[mutant]]
file = "src/pkg/mod.py"
function = "Box"
change = "True -> False"
why = "listed under the class, not the method"
"""
SHOWN = """src/pkg/mod.py:4: <module>: MORE = ['a', 'b'] -> pass
src/pkg/mod.py:4: <module>: ['a', 'b'] -> ['b']
src/pkg/mod.py:4: <module>: ['a', 'b'] -> ['a']
src/pkg/mod.py:8: check: path in items -> path not in items
src/pkg/mod.py:8: check: path is not None -> path is None
src/pkg/mod.py:10: check: contextlib.suppress(OSError) -> __import__('contextlib').nullcontext()
src/pkg/mod.py:13: check: return path < items >= path -> pass
src/pkg/mod.py:13: check: path < items >= path -> path <= items >= path
src/pkg/mod.py:13: check: path < items >= path -> path < items > path
src/pkg/mod.py:14: check: OSError -> ()
src/pkg/mod.py:15: check: return False -> pass
src/pkg/mod.py:15: check: False -> True
src/pkg/mod.py:21: Box.size: return [len(self), True] -> pass
src/pkg/mod.py:21: Box.size: True -> False
src/pkg/mod.py:24: <module>: LAST = ('a', '【') -> pass
src/pkg/mod.py:24: <module>: ('a', '【') -> ('a',)
"""
CALLS = 'def run(log):\n    log.append("b")\n    return [*log, "a"]\n'
CALLS_TEST = 'import calls\n\n\ndef test_run():\n    assert "a" in calls.run([])\n'


def plant(root: Path, files: dict[str, str], changes: dict[str, str | None]) -> str:
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(text.encode())
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    git = ["git", "write-tree"]
    tree = subprocess.run(git, cwd=root, capture_output=True, text=True, check=True)
    for path, text in changes.items():
        if text is None:
            (root / path).unlink()
        else:
            (root / path).write_bytes(text.encode())
    return tree.stdout.strip()


def mutate(root: Path, base: str, listed: str = "") -> subprocess.CompletedProcess[str]:
    (root / "tools" / "mutation").mkdir(parents=True, exist_ok=True)
    (root / "tools" / "mutation" / "equivalent.toml").write_text(listed, "utf-8")
    run = [sys.executable, str(TOOL), base]
    return subprocess.run(run, cwd=root, capture_output=True, encoding="utf-8")


def test_each_change_on_a_changed_line_is_shown_unless_listed(tmp_path: Path) -> None:
    base = plant(tmp_path, {"src/pkg/mod.py": BEFORE}, {"src/pkg/mod.py": AFTER})
    done = mutate(tmp_path, base, LISTED)
    assert (done.stdout, done.returncode) == (SHOWN, 1)
    assert (tmp_path / "src/pkg/mod.py").read_bytes() == AFTER.encode()


def test_tests_ruff_cases_and_removed_files_are_left_out(tmp_path: Path) -> None:
    others = ["src/m/b_measure.py", "conftest.py", "tools/lint/ruff/E1/pr1.py"]
    files = {"src/t/a_test.py": "def test_x():\n    pass\n", "src/gone.py": "X = 1\n"}
    changes = {
        "src/t/a_test.py": "def test_x():\n    assert True\n",
        "src/gone.py": None,
    }
    files |= dict.fromkeys(others, "X = 1\n")
    changes |= dict.fromkeys(others, "X = True\n")
    done = mutate(tmp_path, plant(tmp_path, files, changes))
    assert (done.stdout, done.returncode) == ("", 0)


def test_a_mutant_the_tests_next_to_it_kill_is_not_shown(tmp_path: Path) -> None:
    files = {
        "pkg/calls.py": "def run(log):\n    return log\n",
        "pkg/calls_test.py": CALLS_TEST,
        "bad/calls.py": "def run(log):\n    return log\n",
        "bad/calls_measure.py": "def test_run():\n    assert False\n",
    }
    changes = {"pkg/calls.py": CALLS, "bad/calls.py": CALLS}
    done = mutate(tmp_path, plant(tmp_path, files, changes))
    shown = (
        "bad/calls.py: the tests next to it fail with no change\n"
        "pkg/calls.py:2: run: log.append('b') -> pass\n"
    )
    assert (done.stdout, done.returncode) == (shown, 1)


def test_a_base_git_does_not_know_stops_the_step(tmp_path: Path) -> None:
    plant(tmp_path, {"a.py": "X = 1\n"}, {"a.py": "X = True\n"})
    done = mutate(tmp_path, "no-such-base")
    assert (done.stdout, done.returncode) == ("", 1)
