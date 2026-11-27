import hashlib
import json
from pathlib import Path

import pytest

import test_manifest
from ritmelli.update.keys import KEYS
from ritmelli.update.manifest import Installer, check
from ritmelli.update.verify import Refused

URL = "http://127.0.0.1:8765"


def build_info(folder: Path, version: str) -> Path:
    sha = hashlib.sha256(version.encode()).hexdigest()
    artifacts = {"ritmelli.exe": {"sha256": sha, "size": 1}}
    artifacts[f"Ritmelli-{version}-setup.exe"] = {"sha256": sha, "size": 11264}
    path = folder / f"build-info-{version}.json"
    path.write_text(json.dumps({"version": version, "artifacts": artifacts}), "utf-8")
    return path


def test_each_build_and_the_latest_pass_with_the_key_it_prints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    served = tmp_path / "served"
    infos = [build_info(tmp_path, "0.900.2"), build_info(tmp_path, "0.900.1")]
    test_manifest.main([URL, str(served), *map(str, infos)])
    keys = {1: capsys.readouterr().out.strip()}
    for name, version in (
        ("v0.900.1", "0.900.1"),
        ("v0.900.2", "0.900.2"),
        ("latest", "0.900.2"),
    ):
        data = (served / name / "manifest.json").read_bytes()
        signature = (served / name / "manifest.json.sig").read_bytes()
        found = check(data, signature, keys, https_only=False)
        setup = f"{URL}/v{version}/Ritmelli-{version}-setup.exe"
        sha = hashlib.sha256(version.encode()).hexdigest()
        assert found.version == version
        assert found.installer == Installer(setup, sha, 11264)
        with pytest.raises(Refused, match="signature"):
            check(data, signature, KEYS, https_only=False)
    files = (p for p in served.rglob("*") if p.is_file())
    written = sorted(p.relative_to(served).as_posix() for p in files)
    assert written == [
        f"{name}/manifest.json{end}"
        for name in ("latest", "v0.900.1", "v0.900.2")
        for end in ("", ".sig")
    ]
