"""Minimal client for the Podman REST API, served over a Unix socket."""

import contextlib
import http.client
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.parse
from collections.abc import Callable, Generator
from pathlib import Path

from . import errors
from .command import PodmanCommand

API_VERSION = "v1.41"
SERVICE_START_TIMEOUT = 10
SERVICE_STOP_TIMEOUT = 5


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: Path) -> None:
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(str(self.socket_path))


def _wait_for_service(proc: subprocess.Popen, socket_path: Path) -> None:
    deadline = time.monotonic() + SERVICE_START_TIMEOUT
    while time.monotonic() < deadline:
        ret = proc.poll()
        if ret is not None:
            raise errors.ServiceTerminated(ret)
        conn = UnixHTTPConnection(socket_path)
        try:
            conn.request("GET", "/_ping")
            if conn.getresponse().status == http.client.OK:
                return
        except (OSError, http.client.HTTPException):
            pass
        finally:
            conn.close()
        time.sleep(0.05)
    raise errors.ServiceTimeout(SERVICE_START_TIMEOUT)


@contextlib.contextmanager
def service(podman: PodmanCommand) -> Generator[Path]:
    """Serve the Podman REST API on a private socket, and yield the socket path.

    The service stops on its own a few seconds after its last connection closes,
    so it cannot outlive Dangerzone for long.
    """

    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    with tempfile.TemporaryDirectory(prefix="dangerzone-", dir=runtime_dir) as tmpdir:
        socket_path = Path(tmpdir) / "podman.sock"
        podman.start_service(uri=f"unix://{socket_path}")
        try:
            assert podman.proc_service is not None
            _wait_for_service(podman.proc_service, socket_path)
            yield socket_path
        finally:
            podman.stop_service(timeout=SERVICE_STOP_TIMEOUT)


def pull(
    socket_path: Path, reference: str, progress_callback: Callable[[int, int], None]
) -> None:
    """Pull an image, reporting the downloaded and total bytes as they change."""
    conn = UnixHTTPConnection(socket_path)
    try:
        query = urllib.parse.urlencode({"fromImage": reference})
        conn.request("POST", f"/{API_VERSION}/images/create?{query}")
        resp = conn.getresponse()
        if resp.status != http.client.OK:
            raise errors.PodmanError(
                f"The Podman service replied with status {resp.status}:"
                f" {resp.read().decode(errors='replace').strip()}"
            )

        current: dict[str, int] = {}
        total: dict[str, int] = {}
        for line in resp:
            event = json.loads(line)
            if "error" in event:
                raise errors.PodmanError(event["error"])

            layer = event.get("id")
            detail = event.get("progressDetail") or {}
            if detail.get("total", 0) > 0:
                current[layer] = detail["current"]
                total[layer] = detail["total"]
            elif event.get("status") == "Download complete" and layer in total:
                current[layer] = total[layer]
            else:
                continue
            progress_callback(sum(current.values()), sum(total.values()))

        # The stream ends in the same way whether the pull succeeded or not,
        # so make sure the image is there.
        conn.request(
            "GET", f"/{API_VERSION}/images/{urllib.parse.quote(reference)}/json"
        )
        if conn.getresponse().status != http.client.OK:
            raise errors.PodmanError(f"The image {reference} was not pulled")
    finally:
        conn.close()
