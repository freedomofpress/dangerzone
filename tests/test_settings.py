import json
from pathlib import Path
from unittest.mock import PropertyMock

import pytest
from pytest_mock import MockerFixture

from dangerzone import settings


def test_no_settings_file_creates_new_one(
    mock_settings: Path,
) -> None:
    """Default settings file is created on first run"""
    settings.load()
    assert settings.FILENAME.is_file()

    with settings.FILENAME.open() as settings_file:
        new_settings_dict = json.load(settings_file)
        assert sorted(new_settings_dict.items()) == sorted(
            settings.generate_default_settings().items()
        )


def test_corrupt_settings(mocker: MockerFixture, mock_settings: Path) -> None:
    # Set some broken settings file
    corrupt_settings_dict = "{:}"
    with settings.FILENAME.open("w") as settings_file:
        settings_file.write(corrupt_settings_dict)

    assert settings.FILENAME.is_file()
    settings.load()
    # Check if settings file was reset to the default
    new_settings_dict = json.load(open(settings.FILENAME))
    assert new_settings_dict != corrupt_settings_dict
    assert sorted(new_settings_dict.items()) == sorted(
        settings.generate_default_settings().items()
    )


def test_new_default_setting(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings.save()

    # Ensure new default setting is imported into settings
    mocker.patch(
        "dangerzone.settings.generate_default_settings",
        return_value={"mock_setting": 1},
    )
    settings.load()
    assert settings.get("mock_setting") == 1


def test_new_settings_added(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    # Add new setting
    settings.set("new_setting_autosaved", 20, autosave=True)
    settings.set(
        "new_setting", 10
    )  # XXX has to be afterwards; otherwise this will be saved

    settings.load()
    # Check if new setting persisted
    assert 20 == settings.get("new_setting_autosaved")
    with pytest.raises(KeyError):
        settings.get("new_setting")
