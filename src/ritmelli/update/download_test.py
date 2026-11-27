import hashlib
import http.server
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import ClassVar

import pytest

from ritmelli.update import download

DATA = bytes(range(256)) * (3 << 12)
SIZE = len(DATA)
CUT = download.CHUNK
Step = tuple[str, int | None]


class Planned(http.server.BaseHTTPRequestHandler):
    """Serves DATA with Range, each request by the next step of the plan.

    ("cut", n) sends n bytes and closes, as a network that fell. ("stall", n) sends n
    bytes and stops answering. "ignore" sends it all without looking at Range. "other"
    answers 206 with another piece.
    """

    plan: ClassVar[list[Step]] = []
    ranges: ClassVar[list[str | None]] = []

    def do_GET(self) -> None:
        kind, count = Planned.plan.pop(0) if Planned.plan else ("whole", None)
        asked = self.headers.get("Range")
        Planned.ranges.append(asked)
        first = 0
        if asked and kind not in ("ignore", "other"):
            first = int(asked.removeprefix("bytes=").rstrip("-"))
        if first or kind == "other":
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {first}-{SIZE - 1}/{SIZE}")
        else:
            self.send_response(200)
        self.send_header("Content-Length", str(SIZE - first))
        self.end_headers()
        self.wfile.write(DATA[first:][:count])
        if kind == "stall":
            threading.Event().wait(1.0)


@pytest.fixture
def url() -> Iterator[str]:
    Planned.plan.clear()
    Planned.ranges.clear()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Planned)
    threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/setup.exe"
    server.shutdown()
    server.server_close()


def run(url: str, path: Path, plan: Sequence[Step], waits: list[float]) -> list[float]:
    Planned.plan[:] = plan
    seen: list[float] = []
    with path.open("wb") as out:
        download.download(url, SIZE, out, False, seen.append, waits.append)
    return seen


def test_a_cut_goes_on_from_where_it_stopped(
    url: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    waits: list[float] = []
    seen = run(url, tmp_path / "setup.exe", [("cut", CUT)], waits)
    assert download.sha256(tmp_path / "setup.exe") == hashlib.sha256(DATA).hexdigest()
    assert Planned.ranges == [None, f"bytes={CUT}-"]
    assert waits == [2.0] and seen[-1] == 1.0
    log = capsys.readouterr().out
    assert "stopped at 1.0 of 3.0 MB" in log and log.endswith("again in 2 s\n")


def test_six_cuts_that_move_on_reach_the_end(url: str, tmp_path: Path) -> None:
    waits: list[float] = []
    run(url, tmp_path / "setup.exe", [("cut", 1000)] * 6, waits)
    assert (tmp_path / "setup.exe").read_bytes() == DATA
    assert len(Planned.ranges) == 7 and waits == [2.0] * 6


def test_a_server_that_stops_answering_is_resumed(
    url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(download, "TIMEOUT_S", 0.2)
    run(url, tmp_path / "setup.exe", [("stall", CUT)], [])
    assert (tmp_path / "setup.exe").read_bytes() == DATA
    assert Planned.ranges == [None, f"bytes={CUT}-"]


def test_a_server_that_ignores_the_range_starts_over(url: str, tmp_path: Path) -> None:
    run(url, tmp_path / "setup.exe", [("cut", CUT), ("ignore", None)], [])
    assert (tmp_path / "setup.exe").read_bytes() == DATA
    assert Planned.ranges == [None, f"bytes={CUT}-"]


def test_another_piece_from_the_server_starts_over(url: str, tmp_path: Path) -> None:
    run(url, tmp_path / "setup.exe", [("cut", CUT), ("other", None)], [])
    assert (tmp_path / "setup.exe").read_bytes() == DATA
    assert Planned.ranges == [None, f"bytes={CUT}-", None]


def test_five_stalled_tries_in_a_row_stop_it(url: str, tmp_path: Path) -> None:
    waits: list[float] = []
    with pytest.raises(OSError, match=r"stopped at 0\.0 of 3\.0 MB"):
        run(url, tmp_path / "setup.exe", [("cut", 1000)] + [("cut", 0)] * 5, waits)
    assert len(Planned.ranges) == 6 and waits == [2.0, 2.0, 5.0, 15.0, 30.0]
