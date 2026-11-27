"""The names v0.7.0 left on each PC, which the new line must keep."""

import ctypes
import ntpath

# Windows takes any setup with this id as the same program. The .iss writes it {{...}.
APP_ID = "{320EB2BD-48BC-420D-8F52-C22F644E47D4}"
UPDATE_TASK = "Ritmelli Atualiza"
MIC_TASK = r"\Ritmelli\Microfone"
# The modes and the actions that the tasks, the setup and the uninstall log of v0.7.0
# run. Alone, the update mode is the round of the update task.
UPDATE_MODE, UPDATE_ACTIONS = "--atualizador", ("tarefa", "remove")
MIC_MODE, MIC_ACTIONS = "--microfone", ("instala-todos", "remove")
# The key of the hook, in HKLM, which only an administrator writes.
HOOK_KEY = r"SOFTWARE\Ritmelli\Atualizador"

# The key of the mic setup, in HKLM. At its root, what decides whether the filter DLL
# is replaced.
SAVED_KEY = r"SOFTWARE\Ritmelli\Microfone"


def system32(program: str) -> str:
    """A Windows program by its full path. By bare name Windows looks first in the
    folder of the running exe, and a SYSTEM task would run a program planted there."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    folder = ctypes.create_unicode_buffer(260)
    size = kernel.GetSystemDirectoryW(folder, 260)
    if not 0 < size < 260:
        raise ctypes.WinError(ctypes.get_last_error())
    return ntpath.join(folder.value, program)
