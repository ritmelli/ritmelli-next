import http.server
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from ritmelli.update import download

BODY = bytes(range(256)) * 16


class Whole(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)


@pytest.fixture
def url() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Whole)
    threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/manifest.json"
    server.shutdown()
    server.server_close()


def test_http_only_with_the_hook(url: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="https"):
        download.fetch(url, len(BODY), https_only=True)
    with (tmp_path / "setup.exe").open("wb") as out:
        with pytest.raises(ValueError, match="https"):
            download.download(url, len(BODY), out, True, lambda _: None)
    assert download.fetch(url, len(BODY), https_only=False) == BODY


def test_a_reply_past_the_limit_is_refused(url: str) -> None:
    with pytest.raises(ValueError, match="went over"):
        download.fetch(url, len(BODY) - 1, https_only=False)


def test_a_setup_bigger_than_the_manifest_is_refused(url: str, tmp_path: Path) -> None:
    with (tmp_path / "setup.exe").open("wb") as out:
        with pytest.raises(ValueError, match="bigger"):
            download.download(url, len(BODY) - 1, out, False, lambda _: None)
    assert (tmp_path / "setup.exe").stat().st_size == 0
