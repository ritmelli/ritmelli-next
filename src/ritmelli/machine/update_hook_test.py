import contextlib
import os
import sys
from collections.abc import Callable, Iterator

import pytest

from ritmelli.machine.update_hook import Config, read
from ritmelli.update.keys import KEYS, MANIFEST_URL
from ritmelli.update.verify_test import SEED_PUBLIC

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="the Windows registry")

Hook = Callable[..., Config]


@pytest.fixture
def hook() -> Iterator[Hook]:
    """Writes the values, a str as REG_SZ and an int as a DWORD, in a key of its own
    under HKCU, and reads them as the hook."""
    import winreg

    path = rf"Software\ritmelli-hook-test-{os.getpid()}"

    def write(**values: str | int) -> Config:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            for name, value in values.items():
                kind = winreg.REG_SZ if isinstance(value, str) else winreg.REG_DWORD
                winreg.SetValueEx(key, name, 0, kind, value)
        return read(path, winreg.HKEY_CURRENT_USER)

    yield write
    with contextlib.suppress(FileNotFoundError):
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)


def test_without_the_hook_the_update_reads_production(hook: Hook) -> None:
    production = Config(MANIFEST_URL, KEYS, True)
    assert read(r"Software\ritmelli-hook-test-missing") == production
    assert hook() == production
    assert hook(Manifesto="", Chave="") == production


def test_the_hook_points_the_update_at_a_test_manifest(hook: Hook) -> None:
    url = "http://127.0.0.1:8765/v0.900.1/manifest.json"
    found = hook(Manifesto=url, Chave=SEED_PUBLIC, SoHttps=0)
    assert found == Config(url, {1: SEED_PUBLIC}, False)


def test_so_https_lets_http_in_only_as_the_dword_0(hook: Hook) -> None:
    assert hook(SoHttps="0").https_only
    assert hook(SoHttps=1).https_only
    assert not hook(SoHttps=0).https_only
