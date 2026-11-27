"""Fetching the manifest, its .sig and the setup, as v0.7.0 does."""

import contextlib
import functools
import hashlib
import http.client
import ssl
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO

import certifi

TIMEOUT_S = 20.0
RETRY_WAITS_S = (2.0, 5.0, 15.0, 30.0)
CHUNK = 1 << 20
HEADERS = {"User-Agent": "Ritmelli"}
Progress = Callable[[float], None]


@functools.cache
def _tls() -> ssl.SSLContext:
    """The Windows roots and the certifi ones.

    A new Windows lacks roots until one of its own programs fetches them, so a PC that
    never opened GitHub failed with CERTIFICATE_VERIFY_FAILED. certifi alone is not
    enough: an antivirus that inspects https puts its root only in the Windows list.
    """
    context = ssl.create_default_context()
    with contextlib.suppress(OSError):
        context.load_verify_locations(cafile=certifi.where())
    return context


def _scheme(url: str, https_only: bool) -> None:
    if not url.startswith("https://" if https_only else ("https://", "http://")):
        raise ValueError(f"{url} doesn't come over https")


def fetch(url: str, limit: int, https_only: bool) -> bytes:
    """The whole reply, refused past limit bytes."""
    _scheme(url, https_only)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=TIMEOUT_S, context=_tls()) as reply:
        data: bytes = reply.read(limit + 1)
    if len(data) > limit:
        raise ValueError(f"{url} went over {limit} bytes")
    return data


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(
    url: str,
    size: int,
    out: BinaryIO,
    https_only: bool,
    progress: Progress,
    sleep: Callable[[float], None] = time.sleep,
    timeout: float = TIMEOUT_S,
) -> None:
    """Writes size bytes of url into out, over https unless the hook has SoHttps 0.

    The connection may close before the end with no error: http.client just hands over
    fewer bytes. Then it asks for what is missing, after a wait of RETRY_WAITS_S. A try
    that moved on resets the count. When none of them does, it stops as the network.
    """
    _scheme(url, https_only)
    stalled = 0
    while True:
        before = out.tell()
        reason = _attempt(url, size, out, progress, timeout)
        done = out.tell()
        if done == size:
            return
        stalled = 0 if done > before else stalled + 1
        if stalled > len(RETRY_WAITS_S):
            raise OSError(f"the download stopped at {done} of {size} bytes ({reason})")
        sleep(RETRY_WAITS_S[max(stalled - 1, 0)])


def _attempt(
    url: str, size: int, out: BinaryIO, progress: Progress, timeout: float
) -> object:
    """One request from where out stops. Returns why it ended before size."""
    start = out.tell()
    headers = HEADERS | ({"Range": f"bytes={start}-"} if start else {})
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_tls()) as reply:
            span: str = reply.headers.get("Content-Range", "")
            resumed = reply.status == 206 and span.startswith(f"bytes {start}-")
            if start and not resumed:
                out.seek(0)
                out.truncate()
                if reply.status != 200:
                    return f"the server answered {reply.status} without resuming"
            while chunk := reply.read(CHUNK):
                if out.tell() + len(chunk) > size:
                    raise ValueError("the setup is bigger than the manifest says")
                out.write(chunk)
                progress(out.tell() / size)
    except (OSError, http.client.HTTPException) as error:
        return error
    return "the connection closed before the end"
