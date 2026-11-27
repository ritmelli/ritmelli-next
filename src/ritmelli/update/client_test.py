import hashlib
import http.server
import json
import shutil
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import pytest

from ritmelli.update import client, run_state
from ritmelli.update.verify_test import FIXTURES, SEED_PUBLIC, sign

VERSION, NEW, NEXT = "0.900.1", "0.900.2", "0.900.3"
SETUP = bytes(range(256)) * 64
SHA256 = hashlib.sha256(SETUP).hexdigest()
PID = 4343
STATES = FIXTURES / "state"


class Served(http.server.BaseHTTPRequestHandler):
    """The release: the bytes of each path, and the paths asked for."""

    files: ClassVar[dict[str, bytes]] = {}
    asked: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        Served.asked.append(self.path)
        body = Served.files.get(self.path, b"")
        self.send_response(200 if self.path in Served.files else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


SERVER = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Served)
threading.Thread(target=SERVER.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{SERVER.server_address[1]}"


class Fake:
    """The Windows side: whether Ritmelli is open, and the setups started."""

    def __init__(self, open: bool = False) -> None:
        self.open = open
        self.started: list[list[str]] = []

    def app_open(self) -> bool:
        return self.open

    def alive(self, pid: int) -> bool:
        return False

    def launch(self, argv: Sequence[str]) -> int:
        self.started.append(list(argv))
        return PID


def publish(version: str = NEW, sha256: str = SHA256) -> None:
    """A manifest the test seed signed, with SETUP beside it."""
    installer = {"url": f"{BASE}/setup.exe", "sha256": sha256, "tamanho": len(SETUP)}
    notes = {"notas": ["Uma coisa nova."], "notas_en": ["A new thing."]}
    fields = {"formato": 1, "app": "ritmelli", "versao": version, **notes}
    data = json.dumps({**fields, "instalador": installer}).encode()
    Served.files.update({"/manifest.json": data, "/manifest.json.sig": sign(data)})
    Served.files["/setup.exe"] = SETUP
    Served.asked.clear()


def run(
    folder: Path, machine: Fake | None = None, keys: Mapping[int, str] | None = None
) -> tuple[dict[str, object], Fake]:
    machine = machine or Fake()
    url = f"{BASE}/manifest.json"
    config = client.Config(VERSION, folder, url, keys or {1: SEED_PUBLIC}, False)
    client.run_round(config, machine)
    return run_state.read(folder), machine


def test_no_new_version_downloads_nothing_and_cleans_up(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = ("0.7.0-setup.exe", "0.900.1-setup.exe", "0.900.2-setup.exe.baixando")
    for name in (*old, "0.900.3-setup.exe"):
        (tmp_path / f"Ritmelli-{name}").touch()
    publish(VERSION)
    state, machine = run(tmp_path)
    assert (state["estado"], state["nova"]) == ("parado", None)
    assert "/setup.exe" not in Served.asked and not machine.started
    names = [path.name for path in tmp_path.glob("Ritmelli-*")]
    assert names == ["Ritmelli-0.900.3-setup.exe"]
    log = capsys.readouterr().out
    assert "no new version (installed 0.900.1, published 0.900.1)" in log


def test_an_open_ritmelli_keeps_the_setup_ready_until_it_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "CLOSE_WAIT_S", 0.0)
    publish()
    state, machine = run(tmp_path, Fake(open=True))
    setup = tmp_path / "Ritmelli-0.900.2-setup.exe"
    assert state["estado"] == "pronta" and not machine.started
    assert setup.read_bytes() == SETUP and state["setup"] == setup.name
    shown = json.loads((STATES / "ready.json").read_bytes())["nova"]
    assert state["nova"] == shown | {"versao": NEW, "data": None, "tamanho": len(SETUP)}
    publish()
    machine.open = False
    state, _ = run(tmp_path, machine)
    log = tmp_path / "instalador-0.900.2.log"
    silent = [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]
    assert machine.started == [[*silent, f"/LOG={log}"]]
    assert Served.asked == ["/manifest.json", "/manifest.json.sig"]
    started = [state[key] for key in ("estado", "pid", "versao", "de", "log")]
    assert started == ["instalando", PID, NEW, VERSION, log.name]


def test_the_round_after_a_v0_7_0_install_settles_it_as_done(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """installing.json is the v0.7.0 state with the setup of 0.900.1 started."""
    shutil.copyfile(STATES / "installing.json", tmp_path / run_state.NAME)
    publish(VERSION)
    state, _ = run(tmp_path)
    assert set(json.loads((STATES / "installing.json").read_bytes())) <= set(state)
    settled = (state["estado"], state["instalada"], state["falhas"], state["nova"])
    assert settled == ("parado", VERSION, {}, None) and state.get("erro") is None
    log = capsys.readouterr().out
    assert "previous install: done (0.900.1)" in log and "no new version" in log
