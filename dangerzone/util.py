import inspect
import os
import platform
import shutil
import subprocess
import sys
import appdirs

# If a general-purpose function doesn't depend on anything else in the dangerzone package, then it belongs here.


def get_resource_path(filename):
    if getattr(sys, "dangerzone_dev", False):
        # Look for resources directory relative to python file
        prefix = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(inspect.getfile(inspect.currentframe()))
                )
            ),
            "share",
        )
    else:
        if platform.system() == "Darwin":
            prefix = os.path.join(
                os.path.dirname(os.path.dirname(sys.executable)), "Resources/share"
            )
        elif platform.system() == "Linux":
            prefix = os.path.join(sys.prefix, "share", "dangerzone")
        else:
            # Windows
            prefix = os.path.join(os.path.dirname(sys.executable), "share")
    resource_path = os.path.join(prefix, filename)
    return resource_path


def get_subprocess_startupinfo():
    if platform.system() == "Windows":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return startupinfo
    else:
        return None


def _get_version() -> str:
    """Dangerzone version number. Prefer dangerzone.VERSION to this function."""
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
SYSTEM = platform.system()
CONTAINER_NAME = "dangerzone.rocks/dangerzone"
CONTAINER_COMMAND = "podman" if SYSTEM == "Linux" else "Docker"
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
    "Yoruba": "yor"
}
