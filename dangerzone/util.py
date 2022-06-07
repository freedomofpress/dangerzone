from __future__ import annotations

import gzip
import inspect
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import appdirs

# If a general-purpose function or constant doesn't depend on anything else in the dangerzone package,
# then it belongs here.
from colorama import Back, Fore, Style

import dangerzone

SYSTEM = platform.system()


def dev_mode() -> bool:
    return hasattr(sys, "dangerzone_dev")


def _dev_root_path() -> pathlib.Path:
    """:returns: path to the project root (e.g., /home/user/dangerzone)"""
    frame = inspect.currentframe()
    if frame is None:
        raise SystemError("This Python implementation is missing stack frame support.")
    frame_file = inspect.getfile(frame)  # get the file which defined the current frame
    frame_path = pathlib.Path(frame_file)  # concrete path to frame_file
    frame_abspath = frame_path.resolve()  # resolve any symlinks in frame_path
    project_root = frame_abspath.parent.parent  # grandparent directory of frame_abspath
    return project_root


def get_resource_path(filename: str | os.PathLike[str]) -> str:
    if dev_mode():
        # Look for ./share relative to python file
        prefix = _dev_root_path().joinpath("share")  # e.g., /home/user/dangerzone/share
    elif SYSTEM == "Darwin":
        bin_path = pathlib.Path(
            sys.executable
        )  # /path/to/Dangerzone.app/Contents/MacOS/dangerzone[-cli]
        app_path = bin_path.parent.parent  # /path/to/Dangerzone.app/Contents
        prefix = app_path.joinpath(
            "Resources", "share"
        )  # /path/to/Dangerzone.app/Contents/Resources/share
    elif SYSTEM == "Linux":
        prefix = pathlib.Path(sys.prefix).joinpath("share", "dangerzone")
    elif SYSTEM == "Windows":
        prefix = pathlib.Path(sys.executable).parent.joinpath("share")
    else:
        raise NotImplementedError(f"Unsupported system {SYSTEM}")
    return str(prefix.joinpath(filename))


def get_subprocess_startupinfo():
    if SYSTEM == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None


def _get_version() -> str:
    """Dangerzone version number. Prefer VERSION to this function."""
    try:
        with open(get_resource_path("version.txt")) as f:
            version = f.read().strip()
    except FileNotFoundError:
        # In dev mode, in Windows, get_resource_path doesn't work properly for the container, but luckily
        # it doesn't need to know the version
        version = "unknown"
    return version


VERSION = _get_version()
APPDATA_PATH = appdirs.user_config_dir("dangerzone")
CONTAINER_NAME = "dangerzone.rocks/dangerzone"
CONTAINER_COMMAND = "podman" if SYSTEM == "Linux" else "docker"
CONTAINER_RUNTIME = shutil.which(CONTAINER_COMMAND)

WINDOW_ICON_FILENAME = "dangerzone.ico" if SYSTEM == "Windows" else "icon.png"
WINDOW_ICON_PATH = get_resource_path(WINDOW_ICON_FILENAME)

# Languages supported by tesseract
OCR_LANGUAGES = {
    "Afrikaans": "ar",
    "Albanian": "sqi",
    "Amharic": "amh",
    "Arabic": "ara",
    "Arabic script": "Arabic",
    "Armenian": "hye",
    "Armenian script": "Armenian",
    "Assamese": "asm",
    "Azerbaijani": "aze",
    "Azerbaijani (Cyrillic)": "aze_cyrl",
    "Basque": "eus",
    "Belarusian": "bel",
    "Bengali": "ben",
    "Bengali script": "Bengali",
    "Bosnian": "bos",
    "Breton": "bre",
    "Bulgarian": "bul",
    "Burmese": "mya",
    "Canadian Aboriginal script": "Canadian_Aboriginal",
    "Catalan": "cat",
    "Cebuano": "ceb",
    "Cherokee": "chr",
    "Cherokee script": "Cherokee",
    "Chinese - Simplified": "chi_sim",
    "Chinese - Simplified (vertical)": "chi_sim_vert",
    "Chinese - Traditional": "chi_tra",
    "Chinese - Traditional (vertical)": "chi_tra_vert",
    "Corsican": "cos",
    "Croatian": "hrv",
    "Cyrillic script": "Cyrillic",
    "Czech": "ces",
    "Danish": "dan",
    "Devanagari script": "Devanagari",
    "Divehi": "div",
    "Dutch": "nld",
    "Dzongkha": "dzo",
    "English": "eng",
    "English, Middle (1100-1500)": "enm",
    "Esperanto": "epo",
    "Estonian": "est",
    "Ethiopic script": "Ethiopic",
    "Faroese": "fao",
    "Filipino": "fil",
    "Finnish": "fin",
    "Fraktur script": "Fraktur",
    "Frankish": "frk",
    "French": "fra",
    "French, Middle (ca.1400-1600)": "frm",
    "Frisian (Western)": "fry",
    "Gaelic (Scots)": "gla",
    "Galician": "glg",
    "Georgian": "kat",
    "Georgian script": "Georgian",
    "German": "deu",
    "Greek": "ell",
    "Greek script": "Greek",
    "Gujarati": "guj",
    "Gujarati script": "Gujarati",
    "Gurmukhi script": "Gurmukhi",
    "Hangul script": "Hangul",
    "Hangul (vertical) script": "Hangul_vert",
    "Han - Simplified script": "HanS",
    "Han - Simplified (vertical) script": "HanS_vert",
    "Han - Traditional script": "HanT",
    "Han - Traditional (vertical) script": "HanT_vert",
    "Hatian": "hat",
    "Hebrew": "heb",
    "Hebrew script": "Hebrew",
    "Hindi": "hin",
    "Hungarian": "hun",
    "Icelandic": "isl",
    "Indonesian": "ind",
    "Inuktitut": "iku",
    "Irish": "gle",
    "Italian": "ita",
    "Italian - Old": "ita_old",
    "Japanese": "jpn",
    "Japanese script": "Japanese",
    "Japanese (vertical)": "jpn_vert",
    "Japanese (vertical) script": "Japanese_vert",
    "Javanese": "jav",
    "Kannada": "kan",
    "Kannada script": "Kannada",
    "Kazakh": "kaz",
    "Khmer": "khm",
    "Khmer script": "Khmer",
    "Korean": "kor",
    "Korean (vertical)": "kor_vert",
    "Kurdish (Arabic)": "kur_ara",
    "Kyrgyz": "kir",
    "Lao": "lao",
    "Lao script": "Lao",
    "Latin": "lat",
    "Latin script": "Latin",
    "Latvian": "lav",
    "Lithuanian": "lit",
    "Luxembourgish": "ltz",
    "Macedonian": "mkd",
    "Malayalam": "mal",
    "Malayalam script": "Malayalam",
    "Malay": "msa",
    "Maltese": "mlt",
    "Maori": "mri",
    "Marathi": "mar",
    "Mongolian": "mon",
    "Myanmar script": "Myanmar",
    "Nepali": "nep",
    "Norwegian": "nor",
    "Occitan (post 1500)": "oci",
    "Old Georgian": "kat_old",
    "Oriya (Odia) script": "Oriya",
    "Oriya": "ori",
    "Pashto": "pus",
    "Persian": "fas",
    "Polish": "pol",
    "Portuguese": "por",
    "Punjabi": "pan",
    "Quechua": "que",
    "Romanian": "ron",
    "Russian": "rus",
    "Sanskrit": "san",
    "script and orientation": "osd",
    "Serbian (Latin)": "srp_latn",
    "Serbian": "srp",
    "Sindhi": "snd",
    "Sinhala script": "Sinhala",
    "Sinhala": "sin",
    "Slovakian": "slk",
    "Slovenian": "slv",
    "Spanish, Castilian - Old": "spa_old",
    "Spanish": "spa",
    "Sundanese": "sun",
    "Swahili": "swa",
    "Swedish": "swe",
    "Syriac script": "Syriac",
    "Syriac": "syr",
    "Tajik": "tgk",
    "Tamil script": "Tamil",
    "Tamil": "tam",
    "Tatar": "tat",
    "Telugu script": "Telugu",
    "Telugu": "tel",
    "Thaana script": "Thaana",
    "Thai script": "Thai",
    "Thai": "tha",
    "Tibetan script": "Tibetan",
    "Tibetan Standard": "bod",
    "Tigrinya": "tir",
    "Tonga": "ton",
    "Turkish": "tur",
    "Ukrainian": "ukr",
    "Urdu": "urd",
    "Uyghur": "uig",
    "Uzbek (Cyrillic)": "uzb_cyrl",
    "Uzbek": "uzb",
    "Vietnamese script": "Vietnamese",
    "Vietnamese": "vie",
    "Welsh": "cym",
    "Yiddish": "yid",
    "Yoruba": "yor",
}


def is_container_installed():
    """
    See if the podman container is installed. Linux only.
    """
    # Get the image id
    with open(get_resource_path("image-id.txt")) as f:
        expected_image_id = f.read().strip()

    # See if this image is already installed
    installed = False
    found_image_id = subprocess.check_output(
        [
            CONTAINER_RUNTIME,
            "image",
            "list",
            "--format",
            "{{.ID}}",
            dangerzone.util.CONTAINER_NAME,
        ],
        text=True,
        startupinfo=get_subprocess_startupinfo(),
    )
    found_image_id = found_image_id.strip()

    if found_image_id == expected_image_id:
        installed = True
    elif found_image_id == "":
        pass
    else:
        print("Deleting old dangerzone container image")

        try:
            subprocess.check_output(
                [CONTAINER_RUNTIME, "rmi", "--force", found_image_id],
                startupinfo=get_subprocess_startupinfo(),
            )
        except:
            print("Couldn't delete old container image, so leaving it there")

    return installed


def install_container():
    """
    Make sure the podman container is installed. Linux only.
    """
    if is_container_installed():
        return

    # Load the container into podman
    print("Installing Dangerzone container image...")

    p = subprocess.Popen(
        [CONTAINER_RUNTIME, "load"],
        stdin=subprocess.PIPE,
        startupinfo=get_subprocess_startupinfo(),
    )

    chunk_size = 10240
    compressed_container_path = get_resource_path("container.tar.gz")
    with gzip.open(compressed_container_path) as f:
        while True:
            chunk = f.read(chunk_size)
            if len(chunk) > 0:
                p.stdin.write(chunk)
            else:
                break
    p.communicate()

    if not is_container_installed():
        print("Failed to install the container image")
        return False

    print("Container image installed")
    return True


def display_banner():
    """
    Raw ASCII art example:
    ╭──────────────────────────╮
    │           ▄██▄           │
    │          ██████          │
    │         ███▀▀▀██         │
    │        ███   ████        │
    │       ███   ██████       │
    │      ███   ▀▀▀▀████      │
    │     ███████  ▄██████     │
    │    ███████ ▄█████████    │
    │   ████████████████████   │
    │    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    │
    │                          │
    │    Dangerzone v0.1.5     │
    │ https://dangerzone.rocks │
    ╰──────────────────────────╯
    """

    print(Back.BLACK + Fore.YELLOW + Style.DIM + "╭──────────────────────────╮")
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "           ▄██▄           "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "          ██████          "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "         ███▀▀▀██         "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "        ███   ████        "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "       ███   ██████       "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "      ███   ▀▀▀▀████      "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "     ███████  ▄██████     "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "    ███████ ▄█████████    "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "   ████████████████████   "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Fore.LIGHTYELLOW_EX
        + Style.NORMAL
        + "    ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀    "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(Back.BLACK + Fore.YELLOW + Style.DIM + "│                          │")
    left_spaces = (15 - len(VERSION) - 1) // 2
    right_spaces = left_spaces
    if left_spaces + len(VERSION) + 1 + right_spaces < 15:
        right_spaces += 1
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Style.RESET_ALL
        + Back.BLACK
        + Fore.LIGHTWHITE_EX
        + Style.BRIGHT
        + f"{' '*left_spaces}Dangerzone v{VERSION}{' '*right_spaces}"
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(
        Back.BLACK
        + Fore.YELLOW
        + Style.DIM
        + "│"
        + Style.RESET_ALL
        + Back.BLACK
        + Fore.LIGHTWHITE_EX
        + " https://dangerzone.rocks "
        + Fore.YELLOW
        + Style.DIM
        + "│"
    )
    print(Back.BLACK + Fore.YELLOW + Style.DIM + "╰──────────────────────────╯")
