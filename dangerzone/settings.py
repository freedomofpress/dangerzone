import json
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from packaging import version

from .document import SAFE_EXTENSION
from .util import get_version

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .logic import DangerzoneCore

SETTINGS_FILENAME: str = "settings.json"


class Settings:
    settings: Dict[str, Any]

    def __init__(self, dangerzone: "DangerzoneCore") -> None:
        self.dangerzone = dangerzone
        self.settings_filename = os.path.join(
            self.dangerzone.appdata_path, SETTINGS_FILENAME
        )
        self.default_settings: Dict[str, Any] = self.generate_default_settings()
        self.load()

    @classmethod
    def generate_default_settings(cls) -> Dict[str, Any]:
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

    def get(self, key: str) -> Any:
        return self.settings[key]

    def set(self, key: str, val: Any, autosave: bool = False) -> None:
        try:
            old_val = self.get(key)
        except KeyError:
            old_val = None
        self.settings[key] = val
        if autosave and val != old_val:
            self.save()

    def get_updater_settings(self) -> Dict[str, Any]:
        return {
            key: val for key, val in self.settings.items() if key.startswith("updater_")
        }

    def load(self) -> None:
        if os.path.isfile(self.settings_filename):
            self.settings = self.default_settings

            # If the settings file exists, load it
            try:
                with open(self.settings_filename, "r") as settings_file:
                    self.settings = json.load(settings_file)

                # If it's missing any fields, add them from the default settings
                for key in self.default_settings:
                    if key not in self.settings:
                        self.settings[key] = self.default_settings[key]
                    elif key == "updater_latest_version":
                        if version.parse(get_version()) > version.parse(self.get(key)):
                            self.set(key, get_version())

            except:
                log.error("Error loading settings, falling back to default")
                self.settings = self.default_settings

        else:
            # Save with default settings
            log.info("Settings file doesn't exist, starting with default")
            self.settings = self.default_settings

        self.save()

    def save(self) -> None:
        os.makedirs(self.dangerzone.appdata_path, exist_ok=True)
        with open(self.settings_filename, "w") as settings_file:
            json.dump(self.settings, settings_file, indent=4)
