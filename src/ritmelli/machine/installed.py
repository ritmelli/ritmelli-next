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

# The filter, on the EFX and LFX slots, and the hosts, one per vendor MFX. The
# FxProperties of each microphone point at them, so they never change.
FILTER_CLSID = "{C17A1D48-D473-40D9-9ED3-D024AA46EBE2}"
HOST_CLSIDS = (
    "{D6EB08E6-2DDA-44F3-88C8-2D0EA00C6C8E}",
    "{9FEF5C33-9ED4-4CC6-8624-4F017BB71678}",
    "{ED59B560-1ECA-4491-9179-EC121791159D}",
    "{1663A464-C189-435F-89BD-9C9E9BAF1C23}",
)
OUR_CLSIDS = (FILTER_CLSID, *HOST_CLSIDS)
APO_KEY = r"SOFTWARE\Classes\AudioEngine\AudioProcessingObjects"
CAPTURE_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture"
# The key of the mic setup, in HKLM. Under each microphone id, its original slots.
# At the root, _hospede<n> is the vendor MFX that host n runs, which the filter
# reads, and what decides whether the filter DLL is replaced.
SAVED_KEY, HOSTED, SAVED_VERSION = r"SOFTWARE\Ritmelli\Microfone", "_hospede", 3
# Next to the original slots: the slots the mic setup created, 1 when the audio
# enhancements were off, and the version of the copy.
MISSING, ENHANCEMENTS_OFF, COPY_VERSION = "_ausentes", "_sem_melhorias", "_versao"
# The slots, values of FxProperties. Without the association Windows reads none.
# A driver with no processing modes reads only the LFX.
_FX = "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d}"
_MODES = "{d3993a3f-99c2-4402-b5ec-a92a0367664b}"
ASSOCIATION, LFX, GFX, SFX = f"{_FX},0", f"{_FX},1", f"{_FX},2", f"{_FX},5"
MFX, EFX, MFX_LIST, EFX_LIST = f"{_FX},6", f"{_FX},7", f"{_FX},14", f"{_FX},15"
SFX_MODES, MFX_MODES, EFX_MODES = f"{_MODES},5", f"{_MODES},6", f"{_MODES},7"
MODE_DEFAULT = "{C18E2F7E-933D-4965-B7D1-1EEF228D2AF3}"
MODE_RAW = "{9E90EA20-B493-4FD1-A1A8-7E1361A956CF}"
ANY_NODE = "{00000000-0000-0000-0000-000000000000}"
# In Properties, 1 turns the audio enhancements off, and then no effect loads.
NO_ENHANCEMENTS = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
# What the mic setup saves before it puts the filter on. Of the slots it may create,
# the missing ones go in _ausentes, and come off when the original comes back.
SAVED_SLOTS = (
    *(ASSOCIATION, LFX, GFX, SFX, MFX, EFX, EFX_LIST, MFX_LIST),
    *(SFX_MODES, MFX_MODES, EFX_MODES),
)
CREATED_SLOTS = (ASSOCIATION, LFX, SFX, SFX_MODES, EFX_LIST, EFX_MODES, MFX_LIST)


def system32(program: str) -> str:
    """A Windows program by its full path. By bare name Windows looks first in the
    folder of the running exe, and a SYSTEM task would run a program planted there."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    folder = ctypes.create_unicode_buffer(260)
    size = kernel.GetSystemDirectoryW(folder, 260)
    if not 0 < size < 260:
        raise ctypes.WinError(ctypes.get_last_error())
    return ntpath.join(folder.value, program)
