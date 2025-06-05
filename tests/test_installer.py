from dangerzone.updater.installer import Strategy, get_installation_strategy

installer = "dangerzone.updater.installer"


def test_user_installs_dangerzone_for_the_first_time(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 10)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_upgrades_disabled_detect_wrong_container_upgrade(mocker):
    """
    2. Upgrades are disabled, we want to detect that the locally
    installed container is not the intended one, and upgrade to the new one
    """
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
    mocker.patch(f"{installer}.get_last_log_index", return_value=100)
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_building_dangerzone_from_source_first_time(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 10)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_building_dangerzone_from_source_nth_time(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_enable_updates_after_some_time(mocker):
    """5. Enable updates after some time (same as Enable updates immediately)"""
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_enable_updates_no_new_image_available(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_downgrade_dangerzone_application(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_disable_updates(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_podman_state_reset_updates_enabled(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_podman_state_reset_updates_disabled(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER


def test_upgrade_to_latest_container_via_cli(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.DO_NOTHING


def test_install_new_dangerzone_version_updates_enabled(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 200)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_REMOTE_CONTAINER


def test_airgapped_installation_container_tarball(mocker):
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
    mocker.patch(f"{installer}.BUNDLED_LOG_INDEX", 300)

    result = get_installation_strategy()
    assert result == Strategy.INSTALL_LOCAL_CONTAINER
