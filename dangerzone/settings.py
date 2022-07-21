import json
import logging
import os
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .global_common import GlobalCommon


class Settings:
    def __init__(self, global_common: "GlobalCommon") -> None:
        self.global_common = global_common
        self.settings_filename = os.path.join(
            self.global_common.appdata_path, "settings.json"
        )
        self.default_settings = {
            "save": True,
            "ocr": True,
            "ocr_language": "English",
            "open": True,
            "open_app": None,
        }

        self.load()

    def get(self, key: str):
        return self.settings[key]

    def set(self, key: str, val) -> None:
        self.settings[key] = val

    def load(self) -> None:
        if os.path.isfile(self.settings_filename):
            # If the settings file exists, load it
            try:
                with open(self.settings_filename, "r") as settings_file:
                    self.settings = json.load(settings_file)

                # If it's missing any fields, add them from the default settings
                for key in self.default_settings:
                    if key not in self.settings:
                        self.settings[key] = self.default_settings[key]

            except:
                log.error("Error loading settings, falling back to default")
                self.settings = self.default_settings

        else:
            # Save with default settings
            log.info("Settings file doesn't exist, starting with default")
            self.settings = self.default_settings

        self.save()

    def save(self) -> None:
        os.makedirs(self.global_common.appdata_path, exist_ok=True)
        with open(self.settings_filename, "w") as settings_file:
            json.dump(self.settings, settings_file, indent=4)
