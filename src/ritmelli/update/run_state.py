"""The estado.json of the update task, next to the setups it downloads.

The next round, the screen and the reopen script of v0.7.0 read it. So the keys and the
values on disk stay in Portuguese, as v0.7.0 writes them, and a key this code does not
know stays as it is.
"""

import contextlib
import json
import os
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

NAME = "estado.json"
TRIES = 20


def read(folder: Path) -> dict[str, object]:
    """The state, or {} when the file is missing or does not hold an object."""
    try:
        state: object = json.loads((folder / NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cast(dict[str, object], state) if isinstance(state, dict) else {}


def write(
    folder: Path,
    changes: Mapping[str, object],
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Merges changes into the state on disk and swaps the whole file at once.

    Each write drops the error of the one before and stamps the time, as v0.7.0 does.
    """
    state = {key: value for key, value in read(folder).items() if key != "erro"}
    state.update(changes)
    state["quando"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    folder.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f"{NAME}.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=1)
        _swap(temporary, folder / NAME, sleep)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    return state


def _swap(temporary: str, path: Path, sleep: Callable[[float], None]) -> None:
    """Windows refuses it while the screen reads the file: a round gave up over it."""
    for attempt in range(1, TRIES + 1):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == TRIES:
                raise
            sleep(min(0.05 * attempt, 0.5))
