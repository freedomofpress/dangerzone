import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict

from packaging import version

from .document import SAFE_EXTENSION
from .util import get_config_dir, get_version

log = logging.getLogger(__name__)

SETTINGS_FILENAME = get_config_dir() / "settings.json"

SETTINGS: dict = {}


def generate_default_settings() -> Dict[str, Any]:
    return {
        "save": True,
        "archive": True,
        "ocr": True,
        "ocr_language": "English",
        "open": True,
        "open_app": None,
        "safe_extension": SAFE_EXTENSION,
        "updater_check": None,
        "updater_last_check": None,  # last check in UNIX epoch (secs since 1970)
        # FIXME: How to invalidate those if they change upstream?
        "updater_latest_version": get_version(),
        "updater_latest_changelog": "",
        "updater_errors": 0,
    }


def get(key: str) -> Any:
    return SETTINGS[key]


def set(key: str, val: Any, autosave: bool = False) -> None:
    try:
        old_val = SETTINGS.get(key)
    except KeyError:
        old_val = None
    SETTINGS[key] = val
    if autosave and val != old_val:
        save()


def get_updater_settings() -> Dict[str, Any]:
    return {key: val for key, val in SETTINGS.items() if key.startswith("updater_")}


def load() -> None:
    default_settings = default_settings()
    if SETTINGS_FILENAME.is_file():
        # If the settings file exists, load it
        try:
            with SETTINGS_FILENAME.open("r") as settings_file:
                SETTINGS = json.load(settings_file)

            # If it's missing any fields, add them from the default settings
            for key in default_settings:
                if key not in SETTINGS:
                    SETTINGS[key] = default_settings[key]
                elif key == "updater_latest_version":
                    if version.parse(get_version()) > version.parse(get(key)):
                        set(key, get_version())

        except Exception:
            log.error("Error loading settings, falling back to default")
            SETTINGS = default_settings

    else:
        # Save with default settings
        log.info("Settings file doesn't exist, starting with default")
        SETTINGS = default_settings

    save()


def save() -> None:
    SETTINGS_FILENAME.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILENAME.open("w") as settings_file:
        json.dump(SETTINGS, settings_file, indent=4)
