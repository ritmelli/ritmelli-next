import json

import pytest

from ritmelli.update.keys import KEYS
from ritmelli.update.manifest import check
from ritmelli.update.verify import Refused
from ritmelli.update.verify_test import FIXTURES, SEED_PUBLIC, sign

SEED_KEYS = {1: SEED_PUBLIC}
NEW = (FIXTURES / "test-seed" / "manifest.json").read_bytes()
HTTP = "http://127.0.0.1:8765/v0.900.1/Ritmelli-0.900.1-setup.exe"


def new_with(**fields: object) -> bytes:
    return json.dumps(json.loads(NEW) | fields).encode()


def installer_with(**fields: object) -> bytes:
    return new_with(instalador=json.loads(NEW)["instalador"] | fields)


def test_the_v0_7_0_manifest_is_refused_for_its_app() -> None:
    data = (FIXTURES / "v0.7.0" / "manifest.json").read_bytes()
    signature = (FIXTURES / "v0.7.0" / "manifest.json.sig").read_bytes()
    with pytest.raises(Refused, match="app 'vitrola'"):
        check(data, signature, KEYS)


def test_the_test_seed_manifest_passes_with_the_seed_key() -> None:
    signature = (FIXTURES / "test-seed" / "manifest.json.sig").read_bytes()
    manifest = check(NEW, signature, SEED_KEYS)
    assert (manifest.version, manifest.installer.size) == ("0.900.1", 11264)


def test_a_version_with_a_suffix_is_refused() -> None:
    data = new_with(versao="1.0.0-beta")
    with pytest.raises(Refused, match=r"1\.0\.0-beta"):
        check(data, sign(data), SEED_KEYS)


def test_a_size_that_is_not_an_integer_is_refused() -> None:
    data = installer_with(tamanho=1024.0)
    with pytest.raises(Refused, match="installer is out of format"):
        check(data, sign(data), SEED_KEYS)


def test_http_passes_only_with_the_hook() -> None:
    data = installer_with(url=HTTP)
    with pytest.raises(Refused, match="https"):
        check(data, sign(data), SEED_KEYS)
    assert check(data, sign(data), SEED_KEYS, https_only=False).installer.url == HTTP


def test_the_manifest_and_the_signature_have_a_size_limit() -> None:
    data = NEW + b" " * ((1 << 20) - len(NEW))
    signature = sign(data)
    check(data, signature, SEED_KEYS)
    check(data, signature + b" " * (4096 - len(signature)), SEED_KEYS)
    with pytest.raises(Refused, match="manifest went over"):
        check(data + b" ", sign(data + b" "), SEED_KEYS)
    with pytest.raises(Refused, match="signature went over"):
        check(data, signature + b" " * (4097 - len(signature)), SEED_KEYS)
