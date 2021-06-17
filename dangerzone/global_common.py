import sys
import os
import inspect
import appdirs
import platform
import subprocess
import pipes
import colorama
from colorama import Fore, Back, Style

from .settings import Settings


class GlobalCommon(object):
    """
    The GlobalCommon class is a singleton of shared functionality throughout the app
    """

    def __init__(self):
        # Version
        try:
            with open(self.get_resource_path("version.txt")) as f:
                self.version = f.read().strip()
        except FileNotFoundError:
            # In dev mode, in Windows, get_resource_path doesn't work properly for dangerzone-container, but luckily
            # it doesn't need to know the version
            self.version = "unknown"

        # Initialize terminal colors
        colorama.init(autoreset=True)

        # App data folder
        self.appdata_path = appdirs.user_config_dir("dangerzone")

        # In case we have a custom container
        self.custom_container = None

        # dangerzone-container path
        self.dz_container_path = self.get_dangerzone_container_path()

        # Languages supported by tesseract
        self.ocr_languages = {
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

        # Load settings
        self.settings = Settings(self)

    def display_banner(self):
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
        left_spaces = (15 - len(self.version) - 1) // 2
        right_spaces = left_spaces
        if left_spaces + len(self.version) + 1 + right_spaces < 15:
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
            + f"{' '*left_spaces}Dangerzone v{self.version}{' '*right_spaces}"
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

    def get_container_name(self):
        if self.custom_container:
            return self.custom_container
        else:
            return "docker.io/flmcode/dangerzone"

    def get_resource_path(self, filename):
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

    def get_dangerzone_container_path(self):
        if getattr(sys, "dangerzone_dev", False):
            # Look for resources directory relative to python file
            path = os.path.join(
                os.path.dirname(
                    os.path.dirname(
                        os.path.abspath(inspect.getfile(inspect.currentframe()))
                    )
                ),
                "dev_scripts",
                "dangerzone-container",
            )
            if platform.system() == "Windows":
                path = f"{path}.bat"
            return path
        else:
            if platform.system() == "Darwin":
                return os.path.join(
                    os.path.dirname(sys.executable), "dangerzone-container"
                )
            elif platform.system() == "Windows":
                return os.path.join(
                    os.path.dirname(sys.executable), "dangerzone-container.exe"
                )
            else:
                return "/usr/bin/dangerzone-container"

    def exec_dangerzone_container(self, args):
        args = [self.dz_container_path] + args
        args_str = " ".join(pipes.quote(s) for s in args)
        print(Fore.YELLOW + "> " + Fore.CYAN + args_str)

        # Execute dangerzone-container
        return subprocess.Popen(
            args,
            startupinfo=self.get_subprocess_startupinfo(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def get_subprocess_startupinfo(self):
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            return startupinfo
        else:
            return None

    def container_exists(self, container_name):
        """
        Check if container_name is a valid container. Returns a tuple like:
        (success (boolean), error_message (str))
        """
        # Do we have this container?
        with self.exec_dangerzone_container(
            ["ls", "--container-name", container_name]
        ) as p:
            stdout_data, _ = p.communicate()
            lines = stdout_data.split(b"\n")
            if b"> " in lines[0]:
                stdout_data = b"\n".join(lines[1:])

            # The user canceled, or permission denied
            if p.returncode == 126 or p.returncode == 127:
                return False, "Authorization failed"
                return
            elif p.returncode != 0:
                return False, "Container error"
                return

            # Check the output
            if container_name.encode() not in stdout_data:
                return False, f"Container '{container_name}' not found"

        return True, True

    def validate_convert_to_pixel_output(self, common, output):
        """
        Take the output from the convert to pixels tasks and validate it. Returns
        a tuple like: (success (boolean), error_message (str))
        """
        max_image_width = 10000
        max_image_height = 10000

        # Did we hit an error?
        for line in output.split("\n"):
            if (
                "failed:" in line
                or "The document format is not supported" in line
                or "Error" in line
            ):
                return False, output

        # How many pages was that?
        num_pages = None
        for line in output.split("\n"):
            if line.startswith("Document has "):
                num_pages = line.split(" ")[2]
                break
        if not num_pages or not num_pages.isdigit() or int(num_pages) <= 0:
            return False, "Invalid number of pages returned"
        num_pages = int(num_pages)

        # Make sure we have the files we expect
        expected_filenames = []
        for i in range(1, num_pages + 1):
            expected_filenames += [
                f"page-{i}.rgb",
                f"page-{i}.width",
                f"page-{i}.height",
            ]
        expected_filenames.sort()
        actual_filenames = os.listdir(common.pixel_dir.name)
        actual_filenames.sort()

        if expected_filenames != actual_filenames:
            return (
                False,
                f"We expected these files:\n{expected_filenames}\n\nBut we got these files:\n{actual_filenames}",
            )

        # Make sure the files are the correct sizes
        for i in range(1, num_pages + 1):
            with open(f"{common.pixel_dir.name}/page-{i}.width") as f:
                w_str = f.read().strip()
            with open(f"{common.pixel_dir.name}/page-{i}.height") as f:
                h_str = f.read().strip()
            w = int(w_str)
            h = int(h_str)
            if (
                not w_str.isdigit()
                or not h_str.isdigit()
                or w <= 0
                or w > max_image_width
                or h <= 0
                or h > max_image_height
            ):
                return False, f"Page {i} has invalid geometry"

            # Make sure the RGB file is the correct size
            if os.path.getsize(f"{common.pixel_dir.name}/page-{i}.rgb") != w * h * 3:
                return False, f"Page {i} has an invalid RGB file size"

        return True, True
