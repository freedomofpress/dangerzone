import http.server
import json
import platform
import socketserver
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from dangerzone.podman import api, errors

if platform.system() != "Linux":
    pytest.skip("The Podman REST API is only used on Linux", allow_module_level=True)


class FakePodmanService(socketserver.UnixStreamServer):
    """Reply to pull requests with a canned status and JSON lines."""

    def __init__(self, socket_path: Path) -> None:
        self.status = 200
        self.events: list[dict] = []
        self.image_exists = True
        self.requests: list[str] = []
        super().__init__(str(socket_path), FakePodmanHandler)


class FakePodmanHandler(http.server.BaseHTTPRequestHandler):
    server: FakePodmanService

    def do_POST(self) -> None:
        self.server.requests.append(f"{self.command} {self.path}")
        self.send_response(self.server.status)
        self.end_headers()
        for event in self.server.events:
            self.wfile.write(json.dumps(event).encode() + b"\n")

    def do_GET(self) -> None:
        self.server.requests.append(f"{self.command} {self.path}")
        self.send_response(200 if self.server.image_exists else 404)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def fake_service() -> Iterator[FakePodmanService]:
    # The pytest tmp_path may be too long for a Unix socket.
    with (
        tempfile.TemporaryDirectory() as tmpdir,
        FakePodmanService(Path(tmpdir) / "podman.sock") as server,
    ):
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        yield server
        server.shutdown()
        thread.join()


def pull(server: FakePodmanService) -> list[tuple[int, int]]:
    progress: list[tuple[int, int]] = []
    api.pull(
        Path(str(server.server_address)),
        "ghcr.io/image@sha256:1234",
        lambda current, total: progress.append((current, total)),
    )
    return progress


def downloading(layer: str, current: int, total: int) -> dict:
    return {
        "status": "Downloading",
        "progressDetail": {"current": current, "total": total},
        "id": layer,
    }


def test_pull_reports_progress(fake_service: FakePodmanService) -> None:
    fake_service.events = [
        {"status": "Pulling fs layer", "progressDetail": {}, "id": "layer1"},
        downloading("layer1", 10, 100),
        {"status": "Pulling fs layer", "progressDetail": {}, "id": "layer2"},
        downloading("layer2", 150, 300),
        {"status": "Download complete", "progressDetail": {}, "id": "layer1"},
        {"status": "Download complete", "progressDetail": {}, "id": "layer2"},
        {"status": "Download complete", "progressDetail": {}, "id": "config"},
    ]

    assert pull(fake_service) == [(10, 100), (160, 400), (250, 400), (400, 400)]
    assert fake_service.requests == [
        "POST /v1.41/images/create?fromImage=ghcr.io%2Fimage%40sha256%3A1234",
        "GET /v1.41/images/ghcr.io/image%40sha256%3A1234/json",
    ]


def test_pull_http_error(fake_service: FakePodmanService) -> None:
    fake_service.status = 404
    fake_service.events = [{"message": "manifest unknown"}]

    with pytest.raises(errors.PodmanError, match="404.*manifest unknown"):
        pull(fake_service)


def test_pull_error_event(fake_service: FakePodmanService) -> None:
    fake_service.events = [
        downloading("layer1", 10, 100),
        {"error": "connection reset", "errorDetail": {"message": "connection reset"}},
    ]

    with pytest.raises(errors.PodmanError, match="connection reset"):
        pull(fake_service)


def test_pull_interrupted(fake_service: FakePodmanService) -> None:
    fake_service.events = [downloading("layer1", 10, 100)]
    fake_service.image_exists = False

    with pytest.raises(errors.PodmanError, match="was not pulled"):
        pull(fake_service)


def test_service(
    mocker: MockerFixture, fake_service: FakePodmanService, tmp_path: Path
) -> None:
    mocker.patch("dangerzone.podman.api.get_cache_dir", return_value=tmp_path)
    mocker.patch(
        "tempfile.TemporaryDirectory"
    ).return_value.__enter__.return_value = Path(
        str(fake_service.server_address)
    ).parent
    podman = mocker.MagicMock()
    podman.proc_service.poll.return_value = None

    with api.service(podman) as socket_path:
        assert str(socket_path) == fake_service.server_address
        podman.start_service.assert_called_once_with(uri=f"unix://{socket_path}")
        podman.stop_service.assert_not_called()

    assert fake_service.requests == ["GET /_ping"]
    podman.stop_service.assert_called_once()


def test_service_terminated(mocker: MockerFixture) -> None:
    podman = mocker.MagicMock()
    podman.proc_service.poll.return_value = 125

    with pytest.raises(errors.ServiceTerminated), api.service(podman):
        pytest.fail("The service should not be reported as started")

    podman.stop_service.assert_called_once()


def test_service_timeout(mocker: MockerFixture) -> None:
    mocker.patch("dangerzone.podman.api.SERVICE_START_TIMEOUT", 0.2)
    podman = mocker.MagicMock()
    podman.proc_service.poll.return_value = None

    with pytest.raises(errors.ServiceTimeout), api.service(podman):
        pytest.fail("The service should not be reported as started")

    podman.stop_service.assert_called_once()
