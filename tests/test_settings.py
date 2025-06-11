import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import PropertyMock

import pytest
from pytest_mock import MockerFixture

from dangerzone.settings import SETTINGS_FILENAME, Settings


def default_settings_0_4_1() -> Dict[str, Any]:
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


def save_settings(tmp_path: Path, settings: Dict[str, Any]) -> None:
    """Mimic the way Settings save a dictionary to a settings.json file."""
    settings_filename = tmp_path / "settings.json"
    with open(settings_filename, "w") as settings_file:
        json.dump(settings, settings_file, indent=4)


def test_is_singleton(tmp_path: Path, mocker: MockerFixture) -> None:
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    s1 = Settings()
    s2 = Settings()
    s3 = Settings()
    assert s1 == s2 == s3


def test_no_settings_file_creates_new_one(
    tmp_path: Path,
    mocker: MockerFixture,
) -> None:
    """Default settings file is created on first run"""
    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings = Settings()

    assert settings.settings_filename.is_file()
    with settings.settings_filename.open() as settings_file:
        new_settings_dict = json.load(settings_file)
        assert sorted(new_settings_dict.items()) == sorted(
            settings.generate_default_settings().items()
        )


def test_corrupt_settings(tmp_path: Path, mocker: MockerFixture) -> None:
    # Set some broken settings file
    corrupt_settings_dict = "{:}"
    with (tmp_path / SETTINGS_FILENAME).open("w") as settings_file:
        settings_file.write(corrupt_settings_dict)

    mocker.patch("dangerzone.settings.get_config_dir", return_value=tmp_path)
    settings = Settings()
    assert settings.settings_filename.is_file()

    # Check if settings file was reset to the default
    new_settings_dict = json.load(open(settings.settings_filename))
    assert new_settings_dict != corrupt_settings_dict
    assert sorted(new_settings_dict.items()) == sorted(
        settings.generate_default_settings().items()
    )


def test_new_default_setting(tmp_path: Path, mocker: MockerFixture) -> None:
    settings = Settings()
    settings.save()

    # Ensure new default setting is imported into settings
    mocker.patch(
        "dangerzone.settings.Settings.generate_default_settings",
        return_value={"mock_setting": 1},
    )

    Settings._singleton = None

    settings2 = Settings()
    assert settings2.get("mock_setting") == 1


def test_new_settings_added(tmp_path: Path, mocker: MockerFixture) -> None:
    settings = Settings()

    # Add new setting
    settings.set("new_setting_autosaved", 20, autosave=True)
    settings.set(
        "new_setting", 10
    )  # XXX has to be afterwards; otherwise this will be saved

    # Simulate new app startup (settings recreation)
    Settings._singleton = None
    settings2 = Settings()

    # Check if new setting persisted
    assert 20 == settings2.get("new_setting_autosaved")
    with pytest.raises(KeyError):
        settings2.get("new_setting")
