import json
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from packaging import version

from . import errors
from .document import SAFE_EXTENSION
from .util import get_config_dir, get_version

log = logging.getLogger(__name__)

SETTINGS_FILENAME: str = "settings.json"


class Settings:
    settings: Dict[str, Any]

    # This settings class is a singleton, meaning that all instances of it
    # will point to the actual same object.
    # In case there is a need to disable this behavior (e.g. in the tests)
    # setting `Settings._singleton = None` will force a new instance
    _singleton = None

    def __new__(cls, *args: list, **kwargs: dict) -> "Settings":
        if cls._singleton is None:
            cls._singleton = super(Settings, cls).__new__(cls)
        return cls._singleton

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.settings_filename = get_config_dir() / SETTINGS_FILENAME
        self.default_settings: Dict[str, Any] = self.generate_default_settings()
        # Singletons call multiple times the __init__ method
        if not hasattr(self, "settings"):
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
            "updater_check_all": None,
            "updater_last_check": None,  # last check in UNIX epoch (secs since 1970)
            # FIXME: How to invalidate those if they change upstream?
            "updater_latest_version": get_version(),
            "updater_latest_changelog": "",
            "updater_remote_log_index": 0,
            "updater_errors": 0,
            "stop_other_podman_machines": "ask",
            "successful_first_run": None,
        }

    def custom_runtime_specified(self) -> bool:
        return "container_runtime" in self.settings

    def set_custom_runtime(self, runtime: str, autosave: bool = False) -> Path:
        container_runtime = self.path_from_name(runtime)
        self.settings["container_runtime"] = str(container_runtime)
        if autosave:
            self.save()
        return container_runtime

    def path_from_name(self, name: str) -> Path:
        name_path = Path(name)
        if name_path.is_file():
            return name_path
        else:
            runtime = shutil.which(name_path)
            if runtime is None:
                raise errors.NoContainerTechException(name)
            return Path(runtime)

    def unset_custom_runtime(self) -> None:
        self.settings.pop("container_runtime")
        self.save()

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

            except Exception as e:
                log.error(f"Error loading settings, falling back to default {e}")
                self.settings = self.default_settings

        else:
            # Save with default settings
            log.info("Settings file doesn't exist, starting with default")
            self.settings = self.default_settings

        self.save()

    def save(self) -> None:
        self.settings_filename.parent.mkdir(parents=True, exist_ok=True)
        with self.settings_filename.open("w") as settings_file:
            json.dump(self.settings, settings_file, indent=4)
