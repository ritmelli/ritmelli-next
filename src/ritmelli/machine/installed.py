"""The names v0.7.0 left on each PC, which the new line must keep."""

import ctypes
import ntpath

UPDATE_TASK = "Ritmelli Atualiza"
MIC_TASK = r"\Ritmelli\Microfone"
UPDATE_MODE = "--atualizador"
UPDATE_ACTIONS = ("tarefa", "remove")
MIC_MODE = "--microfone"
MIC_ACTIONS = ("instala-todos", "remove")
HOOK_KEY = r"SOFTWARE\Ritmelli\Atualizador"

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
SAVED_KEY = r"SOFTWARE\Ritmelli\Microfone"
HOSTED = "_hospede"
SAVED_VERSION = 3
SILENT = "_mudos"
MISSING = "_ausentes"
ENHANCEMENTS_OFF = "_sem_melhorias"
COPY_VERSION = "_versao"
_FX = "{d04e05a6-594b-4fb6-a80d-01af5eed7d1d}"
_MODES = "{d3993a3f-99c2-4402-b5ec-a92a0367664b}"
ASSOCIATION = f"{_FX},0"
LFX = f"{_FX},1"
GFX = f"{_FX},2"
SFX = f"{_FX},5"
MFX = f"{_FX},6"
EFX = f"{_FX},7"
MFX_LIST = f"{_FX},14"
EFX_LIST = f"{_FX},15"
SFX_MODES = f"{_MODES},5"
MFX_MODES = f"{_MODES},6"
EFX_MODES = f"{_MODES},7"
MODE_DEFAULT = "{C18E2F7E-933D-4965-B7D1-1EEF228D2AF3}"
MODE_RAW = "{9E90EA20-B493-4FD1-A1A8-7E1361A956CF}"
ANY_NODE = "{00000000-0000-0000-0000-000000000000}"
NO_ENHANCEMENTS = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5"
SAVED_SLOTS = (
    ASSOCIATION,
    LFX,
    GFX,
    SFX,
    MFX,
    EFX,
    EFX_LIST,
    MFX_LIST,
    SFX_MODES,
    MFX_MODES,
    EFX_MODES,
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
