import json
import pathlib
import subprocess
from typing import Any

import pytest
from pytest_mock import MockerFixture

from dangerzone import container_utils, errors, settings


def test_get_podman_path(mocker: MockerFixture) -> None:
    """Test that we get the correct Podman path, depending on the distro.

    We should be getting the default Podman installation (None) on Linux, and the
    vendored path on Windows/macOS. On Windows specifically, it should end with .exe.
    """
    mocker.patch("platform.system", return_value="Linux")
    assert container_utils.get_podman_path() is None

    mocker.patch("platform.system", return_value="Windows")
    path = container_utils.get_podman_path()
    assert str(path).endswith("podman.exe")
    assert "vendor" in str(path)

    mocker.patch("platform.system", return_value="Darwin")
    path = container_utils.get_podman_path()
    assert str(path).endswith("podman")
    assert "vendor" in str(path)


def test_create_containers_conf(mocker: MockerFixture, tmp_path: pathlib.Path) -> None:
    """Test that we don't fail when writing the containers conf file.

    Test that we can write and overwrite the config file for Podman containers, and that
    the intermediate dirs will be created.
    """
    seccomp_path = tmp_path / "seccomp.json"
    mocker.patch("dangerzone.container_utils.SECCOMP_PATH", seccomp_path)
    mocker.patch("os.cpu_count", return_value=4)

    path = tmp_path / "path" / "to" / "containers.conf"
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch("dangerzone.container_utils.CONTAINERS_CONF_PATH", path)
    container_utils.create_containers_conf()
    conf = path.read_text()
    assert "helper_binaries_dir" in conf
    assert "cpus=4" in conf
    assert f'volumes=["{tmp_path}:{tmp_path}:ro"]'.replace("\\", "\\\\") in conf

    container_utils.create_containers_conf()
    assert conf == path.read_text()


def test_init_podman_command(mocker: MockerFixture) -> None:
    cmd = mocker.patch("dangerzone.container_utils.PodmanCommand")

    mocker.patch("platform.system", return_value="Linux")
    container_utils.init_podman_command.cache_clear()
    container_utils.init_podman_command()
    cmd.assert_called_once_with(path=None, env=None, options=None)

    for distro in ["Windows", "Darwin"]:
        mocker.patch("platform.system", return_value=distro)
        cmd.reset_mock()
        container_utils.init_podman_command.cache_clear()
        container_utils.init_podman_command()
        kwargs = cmd.call_args.kwargs
        assert "vendor" in str(kwargs["path"])
        assert kwargs["env"]["CONTAINERS_CONF"] is not None
        assert kwargs["options"] is not None


def test_init_podman_command_custom_runtime(mocker: MockerFixture) -> None:
    # Test custom runtime
    # Test Windows/macOS Podman command (env, connection)
    # Test Linux Podman
    mocker.patch("pathlib.Path.is_file", return_value=True)
    mocker.patch("pathlib.Path.exists", return_value=True)
    runtime = "/some/path/to/podman"
    settings.Settings().set_custom_runtime(runtime)
    cmd = mocker.patch("dangerzone.container_utils.PodmanCommand")

    for distro in ["Linux", "Windows", "Darwin"]:
        cmd.reset_mock()
        mocker.patch("platform.system", return_value=distro)
        container_utils.init_podman_command.cache_clear()
        container_utils.init_podman_command()
        cmd.assert_called_once_with(path=pathlib.Path(runtime), env=None, options=None)

        # Second attempt, should be cached
        cmd.reset_mock()
        container_utils.init_podman_command()
        cmd.assert_not_called()


def test_list_containers(mocker: MockerFixture) -> None:
    """Test that list_containers returns the correct containers."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = (
        "dangerzone-container1\ndangerzone-container2\nother-container"
    )

    # Call the function
    containers = container_utils.list_containers()

    # Check the result
    assert containers == ["dangerzone-container1", "dangerzone-container2"]
    mock_podman.return_value.run.assert_called_once_with(
        ["ps", "-a", "--format", "{{ .Names }}"]
    )


def test_list_containers_empty(mocker: MockerFixture) -> None:
    """Test that list_containers returns an empty list if there are no containers."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = ""

    # Call the function
    containers = container_utils.list_containers()

    # Check the result
    assert containers == []


def test_kill_container(mocker: MockerFixture) -> None:
    """Test that kill_container calls the correct podman command."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

    # Call the function
    container_utils.kill_container("test-container")

    # Check the result
    mock_podman.return_value.run.assert_called_once_with(
        ["kill", "test-container"], check=False, timeout=container_utils.TIMEOUT_KILL
    )


def test_kill_container_timeout(mocker: MockerFixture, caplog: Any) -> None:
    """Test that kill_container logs a warning on timeout."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.side_effect = subprocess.TimeoutExpired(
        "kill", container_utils.TIMEOUT_KILL
    )

    # Call the function
    container_utils.kill_container("test-container")

    # Check the log
    assert "Could not kill container 'test-container'" in caplog.text


def test_kill_container_exception(mocker: MockerFixture, caplog: Any) -> None:
    """Test that kill_container logs an error on exception."""
    # Mock the podman command
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.side_effect = Exception("test error")

    # Call the function
    container_utils.kill_container("test-container")

    # Check the log
    assert (
        "Unexpected error occurred while killing container 'test-container'"
        in caplog.text
    )


def test_load_image_tarball(mocker: MockerFixture) -> None:
    """Test that we can load a tarball and get the digest."""
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
    mock_podman.return_value.run.return_value = "Loaded image: sha256:mydigest"
    digest = container_utils.load_image_tarball(pathlib.Path("/fake/path"))
    assert digest == "sha256:mydigest"


def _make_image_info(
    *,
    id: str = "sha256:abc123",
    names: list[str] | None = None,
    digest: str = "sha256:digest_abc",
    repo_digests: list[str] | None = None,
    name: str = "",
) -> dict:
    """Build a dict mimicking a single entry from `podman images --format json`."""
    if not name:
        name = container_utils.expected_image_name()
    if names is None:
        names = [f"{name}:latest"]
    if repo_digests is None:
        repo_digests = [f"{name}@{digest}"]
    return {
        "Id": id,
        "Names": names,
        "Digest": digest,
        "RepoDigests": repo_digests,
    }


class TestImage:
    """Tests for the container_utils.Image class."""

    def test_init_and_repr(self, mocker: MockerFixture) -> None:
        """Verify `__init__` parses fields and `__repr__` embeds them."""
        shared = "sha256:shared"
        info = _make_image_info(
            digest=shared,
            repo_digests=[f"{container_utils.expected_image_name()}@{shared}"],
        )
        img = container_utils.Image(info)

        # id and names are stored verbatim
        assert img.id == info["Id"]
        assert img.names == info["Names"]

        # local digest is stored as-is
        assert img._local_digest == shared

        # repo digests have the 'name@' prefix stripped
        assert img._repo_digests == [shared]

        # digests list contains no duplicates when local == repo
        assert img.digests.count(shared) == 1

        # repr contains the core fields
        r = repr(img)
        assert img.id in r
        assert str(img.names) in r

    def test_is_dangerzone_image(self, mocker: MockerFixture) -> None:
        """Return True when any name starts with the expected image name."""
        name = container_utils.expected_image_name()

        dz_info = _make_image_info(names=[f"{name}:latest"])
        assert container_utils.Image(dz_info).is_dangerzone_image is True

        other_info = _make_image_info(names=["docker.io/alpine:3.18"])
        assert container_utils.Image(other_info).is_dangerzone_image is False

    def test_platform_digest(self, mocker: MockerFixture) -> None:
        """Return local digest for single-repo images, platform digest for
        multi-arch, and raise for non-Dangerzone images."""
        name = container_utils.expected_image_name()

        # Single repo digest -> local digest is returned
        local = "sha256:local_d"
        single = _make_image_info(digest=local, repo_digests=[f"{name}@{local}"])
        assert container_utils.Image(single).platform_digest == local

        # Two repo digests -> the one different from local is returned
        platform = "sha256:platform_d"
        multi = _make_image_info(
            digest=local,
            repo_digests=[
                f"{name}@{local}",
                f"{name}@{platform}",
            ],
        )
        assert container_utils.Image(multi).platform_digest == platform

        # Non-Dangerzone image -> raises RuntimeError
        other = _make_image_info(names=["docker.io/alpine:3.18"])
        with pytest.raises(RuntimeError, match="Expected a Dangerzone image"):
            _ = container_utils.Image(other).platform_digest

    def test_list(self, mocker: MockerFixture) -> None:
        """Parse `podman images` JSON output into Image instances."""
        mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")
        info1 = _make_image_info(id="sha256:first")
        info2 = _make_image_info(id="sha256:second")
        mock_podman.return_value.run.return_value = json.dumps([info1, info2])

        # Without filter
        images = container_utils.Image.list()
        assert len(images) == 2
        assert images[0].id == "sha256:first"
        assert images[1].id == "sha256:second"
        mock_podman.return_value.run.assert_called_with(["images", "--format", "json"])

        # With filter -> filter is appended to the command
        mock_podman.return_value.run.return_value = json.dumps([info1])
        images = container_utils.Image.list(image_filter="myfilter")
        assert len(images) == 1
        mock_podman.return_value.run.assert_called_with(
            ["images", "--format", "json", "myfilter"]
        )

        # Empty result -> returns empty list
        mock_podman.return_value.run.return_value = "[]"
        assert container_utils.Image.list() == []

    def test_list_dangerzone_images(self, mocker: MockerFixture) -> None:
        """Filter local images by the expected name, excluding others."""
        name = container_utils.expected_image_name()
        mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

        # One Dangerzone image and one unrelated image returned by podman;
        # only the Dangerzone image should appear in the result.
        dz_info = _make_image_info()
        mock_podman.return_value.run.return_value = json.dumps([dz_info])

        images = container_utils.Image.list_dangerzone_images()
        assert len(images) == 1
        assert images[0].id == dz_info["Id"]
        mock_podman.return_value.run.assert_called_once_with(
            ["images", "--format", "json", name]
        )

        # Not found -> raises ImageNotPresentException
        mock_podman.return_value.run.return_value = "[]"
        with pytest.raises(errors.ImageNotPresentException):
            container_utils.Image.list_dangerzone_images()

    def test_get_dangerzone_image(self, mocker: MockerFixture) -> None:
        """Return the single Dangerzone image, or raise if multiple exist."""
        mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

        # Single image -> returned
        info = _make_image_info()
        mock_podman.return_value.run.return_value = json.dumps([info])
        img = container_utils.Image.get_dangerzone_image()
        assert img.id == info["Id"]

        # Multiple images -> raises
        info2 = _make_image_info(id="sha256:second")
        mock_podman.return_value.run.return_value = json.dumps([info, info2])
        with pytest.raises(errors.MultipleImagesFoundException):
            container_utils.Image.get_dangerzone_image()

    def test_from_digest(self, mocker: MockerFixture) -> None:
        """Find an image by digest, normalizing bare hashes automatically."""
        mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

        target = "sha256:target"
        info = _make_image_info(
            digest=target,
            repo_digests=[f"{container_utils.expected_image_name()}@{target}"],
        )
        mock_podman.return_value.run.return_value = json.dumps([info])

        # Exact digest -> found
        img = container_utils.Image.from_digest(target)
        assert target in img.digests

        # Missing digest -> raises
        with pytest.raises(errors.ImageNotPresentException):
            container_utils.Image.from_digest("sha256:nonexistent")

        # Bare hash (no sha256: prefix) -> normalized before lookup
        bare = "abc123"
        normalized = f"sha256:{bare}"
        info_norm = _make_image_info(
            digest=normalized,
            repo_digests=[f"{container_utils.expected_image_name()}@{normalized}"],
        )
        mock_podman.return_value.run.return_value = json.dumps([info_norm])
        img = container_utils.Image.from_digest(bare)
        assert normalized in img.digests


def test_clear_old_images_deletes_digests(mocker: MockerFixture) -> None:
    """Verify that `clear_old_images` removes digests not matching the keep list."""
    name = container_utils.expected_image_name()

    old_digest = "sha256:old_digest"
    new_digest = "sha256:new_digest"
    old_info = _make_image_info(
        digest=old_digest,
        repo_digests=[f"{name}@{old_digest}"],
    )
    new_info = _make_image_info(
        id="sha256:new",
        digest=new_digest,
        repo_digests=[f"{name}@{new_digest}"],
    )

    # Mock Image.list_dangerzone_images to return both old and new images
    mocker.patch(
        "dangerzone.container_utils.Image.list_dangerzone_images",
        return_value=[
            container_utils.Image(old_info),
            container_utils.Image(new_info),
        ],
    )
    mock_podman = mocker.patch("dangerzone.container_utils.init_podman_command")

    container_utils.clear_old_images(digest_to_keep=new_digest)

    # Only the old image's digest should be deleted
    mock_podman.return_value.run.assert_called_once_with(
        ["rmi", "--force", f"{name}@{old_digest}"]
    )

    # Single image reported -> nothing should be cleared
    mock_podman.reset_mock()
    single_info = _make_image_info(
        digest=new_digest,
        repo_digests=[f"{name}@{new_digest}"],
    )
    mocker.patch(
        "dangerzone.container_utils.Image.list_dangerzone_images",
        return_value=[container_utils.Image(single_info)],
    )
    container_utils.clear_old_images(digest_to_keep=new_digest)
    mock_podman.return_value.run.assert_not_called()
