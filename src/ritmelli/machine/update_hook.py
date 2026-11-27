"""The hook: values in HKLM that point the update task at a test manifest. Only an
administrator writes there. v0.7.0 reads the same three values with the same meaning,
so one test manifest serves both."""

import contextlib
from collections.abc import Mapping
from typing import NamedTuple

from ritmelli.machine.installed import HOOK_KEY
from ritmelli.update.keys import KEYS, MANIFEST_URL


class Config(NamedTuple):
    manifest_url: str
    keys: Mapping[int, str]
    https_only: bool


def read(path: str = HOOK_KEY, root: int | None = None) -> Config:
    """Where the update reads the manifest, the keys it trusts, and whether the setup
    must come over https. root is HKLM unless a test passes another.

    Manifesto replaces the address. Chave replaces both production keys as key 1, so a
    .sig by a throwaway key passes only on a PC with the hook. SoHttps lets http in only
    as the DWORD 0: the text "0" does not.
    """
    import winreg  # here, so the module imports on Linux

    values: dict[str, object] = {}
    hive = winreg.HKEY_LOCAL_MACHINE if root is None else root
    with contextlib.suppress(OSError), winreg.OpenKey(hive, path) as key:
        for name in ("Manifesto", "Chave", "SoHttps"):
            with contextlib.suppress(OSError):
                values[name] = winreg.QueryValueEx(key, name)[0]
    manifest, public = values.get("Manifesto"), values.get("Chave")
    return Config(
        manifest_url=str(manifest) if manifest else MANIFEST_URL,
        keys={1: str(public)} if public else KEYS,
        https_only=values.get("SoHttps") != 0,
    )
