import subprocess
import sys
from pathlib import Path

GUARD = 'if sys.platform == "win32":\n    import winreg\n'
INSIDE = "    import winreg\n\n"
TOP = "from typing import NamedTuple\n"
LAZY = "    from PyInstaller.archive.readers import CArchiveReader\n\n"
CASES = [
    ("filter_dll.py:20", "src/ritmelli/machine/filter_dll.py", [(GUARD, "import winreg\n")],
     ["src/ritmelli/machine/filter_dll_test.py"], "No module named 'winreg'"),
    ("mic_check.py:18", "src/ritmelli/machine/mic_check.py", [(GUARD, "import winreg\n")],
     ["src/ritmelli/machine/mic_check_test.py"], "No module named 'winreg'"),
    ("mic_slots.py:46", "src/ritmelli/machine/mic_slots.py", [(GUARD, "import winreg\n")],
     ["src/ritmelli/machine/mic_slots_test.py", "src/ritmelli/machine/mic_setup_test.py"],
     "No module named 'winreg'"),
    ("update_hook.py:27", "src/ritmelli/machine/update_hook.py",
     [(INSIDE, ""), (TOP, TOP + "import winreg\n")],
     ["src/ritmelli/app_test.py", "src/ritmelli/machine/update_hook_test.py"],
     "No module named 'winreg'"),
    ("third_party.py:65", "installer/third_party.py",
     [(LAZY, "\n"), ("from pathlib import Path\n",
                     "from pathlib import Path\n\nfrom PyInstaller.archive.readers import CArchiveReader\n")],
     ["installer/third_party_test.py"], "No module named 'PyInstaller'"),
]


def pytest(tests: list[str]) -> tuple[int, str]:
    done = subprocess.run(["uv", "run", "pytest", "-p", "no:cacheprovider", *tests],
                          capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def last(output: str) -> str:
    return output.strip().splitlines()[-1]


failed = 0
for name, path, edits, tests, error in CASES:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    for old, new in edits:
        assert text.count(old) == 1, (name, old)
        text = text.replace(old, new)
    target.write_text(text, encoding="utf-8")
    try:
        red, red_out = pytest(tests)
    finally:
        subprocess.run(["git", "checkout", "--", path], check=True)
    green, green_out = pytest(tests)
    collected = "ERROR collecting" in red_out and error in red_out
    ok = red == 2 and collected and green == 0
    failed += not ok
    print(f"::group::{name} undone: exit {red}")
    print(red_out)
    print("::endgroup::")
    print(f"{'PASS' if ok else 'FAIL'} {name}: undone exit {red} ({error}: {collected}), "
          f"{last(red_out)}; as merged exit {green}, {last(green_out)}")
clean = subprocess.run(["git", "diff", "--quiet"]).returncode == 0
print(f"tree restored: {clean}")
sys.exit(1 if failed or not clean else 0)
