from unittest.mock import MagicMock

from pytest_mock import MockerFixture

from dangerzone.updater.installer import Strategy, apply_installation_strategy


def test_apply_installation_strategy_local(mocker: MockerFixture) -> None:
    """Test that we clear old images when installing a local container."""
    mock_install_local = mocker.patch(
        "dangerzone.updater.installer.install_local_container_tar"
    )
    mock_install_local.return_value = "local_digest"
    mock_clear_old_images = mocker.patch(
        "dangerzone.updater.installer.runtime.clear_old_images"
    )
    mocker.patch("dangerzone.updater.installer.log")

    apply_installation_strategy(Strategy.INSTALL_LOCAL_CONTAINER)

    mock_install_local.assert_called_once()
    mock_clear_old_images.assert_called_once_with(digest_to_keep="local_digest")


def test_apply_installation_strategy_remote(mocker: MockerFixture) -> None:
    """Test that we clear old images when installing a remote container."""
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
    mocker.patch("dangerzone.updater.installer.log")

    apply_installation_strategy(Strategy.INSTALL_REMOTE_CONTAINER)

    mock_get_remote_digest.assert_called_once_with("some_image_name")
    mock_upgrade.assert_called_once_with("remote_digest", signatures=[{}])
    mock_clear_old_images.assert_called_once_with(digest_to_keep="remote_digest")
