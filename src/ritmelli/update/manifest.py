"""The manifest of a version, read with the limits and the format of v0.7.0, so one
manifest passes both readers. Only app "ritmelli" passes. The partial setup and the
file list are ignored: the new line never uses them."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from ritmelli.update.verify import Refused, verify

FORMAT = 1
APP = "ritmelli"
MANIFEST_MAX = 1 << 20
SIGNATURE_MAX = 4096
SETUP_MAX = 1 << 30
NOTES_MAX = 30
NOTE_MAX = 500


@dataclass(frozen=True)
class Installer:
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Manifest:
    version: str
    date: str | None
    notes: tuple[str, ...]
    notes_en: tuple[str, ...]
    installer: Installer


def parse_version(text: str) -> tuple[int, int, int]:
    """Semver without a suffix: "0.12.3" -> (0, 12, 3)."""
    match = re.fullmatch(r"(\d{1,4})\.(\d{1,4})\.(\d{1,6})", text)
    if not match:
        raise Refused(f"version out of format: {text!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def check(
    data: bytes, signature: bytes, keys: Mapping[int, str], *, https_only: bool = True
) -> Manifest:
    """The manifest, if one of keys signed it and it is in format; otherwise a
    ValueError, Refused when a check fails. https_only False is the hook's SoHttps 0:
    the setup may come over http."""
    if len(data) > MANIFEST_MAX:
        raise Refused(f"the manifest went over {MANIFEST_MAX} bytes")
    if len(signature) > SIGNATURE_MAX:
        raise Refused(f"the signature went over {SIGNATURE_MAX} bytes")
    verify(data, signature, keys)
    raw: object = json.loads(data)
    fields: dict[str, object] = (
        cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    )
    formato, app = fields.get("formato"), fields.get("app")
    if formato != FORMAT or app != APP:
        raise Refused(
            f"the manifest is not for this app: formato {formato!r}, app {app!r}"
        )
    version = str(fields.get("versao"))
    parse_version(version)
    date = fields.get("data")
    return Manifest(
        version=version,
        date=date if isinstance(date, str) else None,
        notes=_notes(fields.get("notas", [])),
        notes_en=_notes(fields.get("notas_en", [])),
        installer=_installer(fields.get("instalador"), https_only),
    )


def _notes(value: object) -> tuple[str, ...]:
    items = cast(list[object], value) if isinstance(value, list) else None
    notes = tuple(n for n in items or () if isinstance(n, str) and len(n) <= NOTE_MAX)
    if items is None or len(items) > NOTES_MAX or len(notes) != len(items):
        raise Refused("the release notes are out of format")
    return notes


def _installer(value: object, https_only: bool) -> Installer:
    entry: dict[str, object] = (
        cast(dict[str, object], value) if isinstance(value, dict) else {}
    )
    url, sha256, size = entry.get("url"), entry.get("sha256"), entry.get("tamanho")
    if not (
        isinstance(url, str)
        and isinstance(sha256, str)
        and re.fullmatch(r"[0-9a-f]{64}", sha256)
        and isinstance(size, int)
        and 0 < size <= SETUP_MAX
    ):
        raise Refused("the manifest installer is out of format")
    if not url.startswith("https://" if https_only else ("https://", "http://")):
        raise Refused("the manifest installer doesn't come over https")
    return Installer(url, sha256, size)
