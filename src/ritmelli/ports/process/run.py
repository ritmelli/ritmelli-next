import subprocess
from collections.abc import Sequence
from pathlib import Path


def run(argv: Sequence[str], timeout: float) -> tuple[int, str]:
    """Runs a program with no window and waits for it: its exit code, and stdout and
    stderr together.

    The program goes by its full path. By bare name, Windows looks first in the folder
    of the running exe, and a SYSTEM task would run a program planted there. Past
    timeout seconds the program is killed and TimeoutError is raised, which a caller
    catches without subprocess.
    """
    if not Path(argv[0]).is_absolute():
        raise ValueError(f"{argv[0]}: give the full path of the program")
    try:
        done = subprocess.run(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
            encoding="oem",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as error:
        raise TimeoutError(f"{argv[0]} ran past {timeout} s") from error
    return done.returncode, done.stdout


def spawn_detached(argv: Sequence[str]) -> int:
    """Starts a program that outlives us, with no console, and returns its pid.

    It leaves our job when Windows allows it, so the end of the update task does not
    take a setup down in the middle. A job that refuses keeps it inside. Only for a
    program that is not a console program, such as a setup: PowerShell started this
    way exits without running its command.
    """
    flags = (
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
        | subprocess.CREATE_NO_WINDOW
    )
    breakaway = flags | subprocess.CREATE_BREAKAWAY_FROM_JOB
    try:
        return subprocess.Popen(argv, creationflags=breakaway, close_fds=True).pid
    except OSError:
        return subprocess.Popen(argv, creationflags=flags, close_fds=True).pid
