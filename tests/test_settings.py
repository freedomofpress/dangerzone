import collections
import json
import os
from pathlib import Path
from unittest.mock import PropertyMock

import pytest
from pytest_mock import MockerFixture

from dangerzone.settings import *


def default_settings_0_4_1() -> dict:
    """Get the default settings for the 0.4.1 Dangerzone release."""
    return {
        "save": True,
        "archive": True,
        "ocr": True,
        "ocr_language": "English",
        "open": True,
        "open_app": None,
        "safe_extension": "-safe.pdf",
    }


@pytest.fixture
def settings(tmp_path: Path, mocker: MockerFixture) -> Settings:
    dz_core = mocker.MagicMock()
    type(dz_core).appdata_path = PropertyMock(return_value=tmp_path)
    return Settings(dz_core)


def save_settings(tmp_path: Path, settings: dict) -> None:
    """Mimic the way Settings save a dictionary to a settings.json file."""
    settings_filename = tmp_path / "settings.json"
    with open(settings_filename, "w") as settings_file:
        json.dump(settings, settings_file, indent=4)


def test_no_settings_file_creates_new_one(settings: Settings) -> None:
    """Default settings file is created on first run"""
    assert os.path.isfile(settings.settings_filename)
    new_settings_dict = json.load(open(settings.settings_filename))
    assert sorted(new_settings_dict.items()) == sorted(
        settings.generate_default_settings().items()
    )


def test_corrupt_settings(tmp_path: Path, mocker: MockerFixture) -> None:
    # Set some broken settings file
    corrupt_settings_dict = "{:}"
    with open(tmp_path / SETTINGS_FILENAME, "w") as settings_file:
        settings_file.write(corrupt_settings_dict)

    # Initialize settings
    dz_core = mocker.MagicMock()
    type(dz_core).appdata_path = PropertyMock(return_value=tmp_path)
    settings = Settings(dz_core)
    assert os.path.isfile(settings.settings_filename)

    # Check if settings file was reset to the default
    new_settings_dict = json.load(open(settings.settings_filename))
    assert new_settings_dict != corrupt_settings_dict
    assert sorted(new_settings_dict.items()) == sorted(
        settings.generate_default_settings().items()
    )


def test_new_default_setting(tmp_path: Path, mocker: MockerFixture) -> None:
    # Initialize settings
    dz_core = mocker.MagicMock()
    type(dz_core).appdata_path = PropertyMock(return_value=tmp_path)
    settings = Settings(dz_core)
    settings.save()

    # Ensure new default setting is imported into settings
    with mocker.patch(
        "dangerzone.settings.Settings.generate_default_settings",
        return_value={"mock_setting": 1},
    ):
        settings2 = Settings(dz_core)
        assert settings2.get("mock_setting") == 1


def test_new_settings_added(tmp_path: Path, mocker: MockerFixture) -> None:
    # Initialize settings
    dz_core = mocker.MagicMock()
    type(dz_core).appdata_path = PropertyMock(return_value=tmp_path)
    settings = Settings(dz_core)

    # Add new setting
    settings.set("new_setting_autosaved", 20, autosave=True)
    settings.set(
        "new_setting", 10
    )  # XXX has to be afterwards; otherwise this will be saved

    # Simulate new app startup (settings recreation)
    settings2 = Settings(dz_core)

    # Check if new setting persisted
    assert 20 == settings2.get("new_setting_autosaved")
    with pytest.raises(KeyError):
        settings2.get("new_setting")
