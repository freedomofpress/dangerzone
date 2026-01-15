from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from dangerzone.updater import SignatureError, UpdaterError
from dangerzone.updater.installer import (
    Strategy,
    apply_installation_strategy,
    get_installation_strategy,
)

installer = "dangerzone.updater.installer"


def test_install_raise_if_local_image_cant_be_installed(
    mocker: MockerFixture,
) -> None:
    """When an image installation fails, an exception should be raised"""

    mocker.patch(
        "dangerzone.updater.installer.install_local_container_tar",
        side_effect=UpdaterError,
    )

    with pytest.raises(UpdaterError):
        apply_installation_strategy(Strategy.INSTALL_LOCAL_CONTAINER)


def test_user_installs_dangerzone_for_the_first_time(mocker: MockerFixture) -> None:
    """1. User installs Dangerzone for the first time"""
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 10)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_upgrades_disabled_detect_wrong_container_upgrade(
    mocker: MockerFixture,
) -> None:
    """
    2. Upgrades are disabled, we want to detect that the locally
    installed container is not the intended one, and upgrade to the new one.
    We also test that old images are cleared.
    """
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["old_digest_1", "old_digest_2"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=100)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    # Check that we get the right strategy
    strategy = get_installation_strategy()
    assert strategy == Strategy.INSTALL_LOCAL_CONTAINER

    # Now, check that applying the strategy works as intended
    mock_install_local = mocker.patch(
        "dangerzone.updater.installer.install_local_container_tar"
    )
    mock_install_local.return_value = "local_digest"
    mock_clear_old_images = mocker.patch(
        "dangerzone.updater.installer.runtime.clear_old_images"
    )

    apply_installation_strategy(strategy)

    mock_install_local.assert_called_once()
    mock_clear_old_images.assert_called_once_with(digest_to_keep="local_digest")


def test_building_dangerzone_from_source_first_time(mocker: MockerFixture) -> None:
    """3. Building Dangerzone from source for the first time (with container image)"""
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 10)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_building_dangerzone_from_source_nth_time(mocker: MockerFixture) -> None:
    """4. Building Dangerzone from source for the Nth time (with container image)"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_enable_updates_after_some_time(mocker: MockerFixture) -> None:
    """
    5. Enable updates after some time (same as Enable updates immediately).
    We also test that old images are cleared.
    """
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["old_digest_1", "old_digest_2"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 300,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    # Check that we get the right strategy
    strategy = get_installation_strategy()
    assert strategy == Strategy.INSTALL_REMOTE_CONTAINER

    # Now, check that applying the strategy works as intended
    mock_get_remote_digest = mocker.patch(
        "dangerzone.updater.installer.get_remote_digest_and_logindex"
    )
    mock_get_remote_digest.return_value = ("remote_digest", 0, [{}])
    mock_upgrade = mocker.patch("dangerzone.updater.installer.upgrade_container_image")
    mock_clear_old_images = mocker.patch(
        "dangerzone.updater.installer.runtime.clear_old_images"
    )
    mocker.patch(
        "dangerzone.updater.installer.runtime.expected_image_name",
        return_value="some_image_name",
    )

    apply_installation_strategy(strategy)

    mock_get_remote_digest.assert_called_once_with("some_image_name")
    mock_upgrade.assert_called_once_with("remote_digest", signatures=[{}])
    mock_clear_old_images.assert_called_once_with(digest_to_keep="remote_digest")


def test_enable_updates_no_new_image_available(mocker: MockerFixture) -> None:
    """6. Enables updates but there is no new image available"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 200,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_downgrade_dangerzone_application(mocker: MockerFixture) -> None:
    """7. Downgrade dangerzone application (v0.10.0 to v0.9.0)"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=300)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_disable_updates(mocker: MockerFixture) -> None:
    """8. Disable updates"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=300)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_podman_state_reset_updates_enabled(mocker: MockerFixture) -> None:
    """9a. Podman state is reset and updates are enabled"""
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 300,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_podman_state_reset_updates_disabled(mocker: MockerFixture) -> None:
    """9b. Podman state is reset and updates are disabled"""
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_upgrade_to_latest_container_via_cli(mocker: MockerFixture) -> None:
    """10. Upgrade to the latest container image via the CLI"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 200,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_install_new_dangerzone_version_updates_enabled(mocker: MockerFixture) -> None:
    """11. Install a new Dangerzone version with updates enabled"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 300,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 200)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_airgapped_installation_container_tarball(mocker: MockerFixture) -> None:
    """12. Airgapped installation of a container tarball"""
    mocker.patch(
        f"{installer}.runtime.list_image_digests",
        return_value=["ghcr.io/freedomofpress/dangerzone/v1:latest"],
    )
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=True)
    mocker.patch(f"{installer}.get_last_log_index", return_value=200)
    mocker.patch(f"{installer}.LAST_KNOWN_LOG_INDEX", 300)
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=True)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_no_bundled_container_tar_first_install(mocker: MockerFixture) -> None:
    """User installs dangerzone-slim (no container.tar) for the first time.

    Without a bundled container, the strategy should fall back to remote
    installation if updates are enabled.
    """
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": True,
        "updater_remote_log_index": 300,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    # No container.tar bundled, so is_container_tar_bundled returns False
    # making bundled_log_index effectively 0
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=False)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_no_bundled_container_tar_updates_disabled(mocker: MockerFixture) -> None:
    """User installs dangerzone-slim (no container.tar) with updates disabled.

    Without a bundled container and with updates disabled, the strategy
    should be DO_NOTHING if there's already an image installed, or
    INSTALL_REMOTE_CONTAINER if there's no image (since max would be 0).
    In this case, with no images and no remote updates, max_log_index is 0
    and local_log_index is 0, so DO_NOTHING is returned.
    """
    mocker.patch(f"{installer}.runtime.list_image_digests", return_value=[])
    mocker.patch(
        f"{installer}.runtime.expected_image_name",
        return_value="ghcr.io/freedomofpress/dangerzone/v1",
    )
    mocker.patch(f"{installer}.Settings").return_value.get.side_effect = lambda key: {
        "updater_check_all": False,
    }.get(key)
    mocker.patch(f"dangerzone.updater.signatures.Path.exists", return_value=False)
    # No container.tar bundled, so is_container_tar_bundled returns False
    # making bundled_log_index effectively 0
    mocker.patch(f"{installer}.is_container_tar_bundled", return_value=False)

    result = get_installation_strategy()
    # With all indexes at 0, local_log_index == max_log_index, so DO_NOTHING
    assert result == Strategy.DO_NOTHING
