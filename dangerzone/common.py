import sys
import os
import inspect
import tempfile
import appdirs
import platform
import subprocess
import shlex
from PyQt5 import QtGui

if platform.system() == "Darwin":
    import CoreServices
    import LaunchServices
    import plistlib

elif platform.system() == "Linux":
    from xdg.DesktopEntry import DesktopEntry

from .settings import Settings


class Common(object):
    """
    The Common class is a singleton of shared functionality throughout the app
    """

    def __init__(self, app):
        # Qt app
        self.app = app

        # Temporary directory to store pixel data
        # Note in macOS, temp dirs must be in /tmp (or a few other paths) for Docker to mount them
        self.pixel_dir = tempfile.TemporaryDirectory(prefix="/tmp/dangerzone-pixel-")
        self.safe_dir = tempfile.TemporaryDirectory(prefix="/tmp/dangerzone-safe-")
        print(
            f"Temporary directories created, dangerous={self.pixel_dir.name}, safe={self.safe_dir.name}"
        )

        # Name of input file
        self.document_filename = None

        # Name of output file
        self.save_filename = None

        # Preload font
        self.fixed_font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)

        # App data folder
        self.appdata_path = appdirs.user_config_dir("dangerzone")

        # Container runtime
        if platform.system() == "Darwin":
            self.container_runtime = "docker"
        else:
            self.container_runtime = "podman"

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

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

    def set_document_filename(self, filename):
        self.document_filename = filename

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
            # In linux...
            prefix = os.path.join(sys.prefix, "share/dangerzone")

        resource_path = os.path.join(prefix, filename)
        return resource_path

    def open_find_viewer(self, filename):
        if self.settings.get("open_app") in self.pdf_viewers:
            if platform.system() == "Darwin":
                # Get the PDF reader bundle command
                bundle_identifier = self.pdf_viewers[self.settings.get("open_app")]
                args = ["open", "-b", bundle_identifier, filename]

                # Run
                print(f"Executing: {' '.join(args)}")
                subprocess.run(args)

            elif platform.system() == "Linux":
                # Get the PDF reader command
                args = shlex.split(self.pdf_viewers[self.settings.get("open_app")])
                # %f, %F, %u, and %U are filenames or URLS -- so replace with the file to open
                for i in range(len(args)):
                    if (
                        args[i] == "%f"
                        or args[i] == "%F"
                        or args[i] == "%u"
                        or args[i] == "%U"
                    ):
                        args[i] = filename

                # Open as a background process
                print(f"Executing: {' '.join(args)}")
                subprocess.Popen(args)

    def _find_pdf_viewers(self):
        pdf_viewers = {}

        if platform.system() == "Darwin":
            # Get all installed apps that can open PDFs
            bundle_identifiers = LaunchServices.LSCopyAllRoleHandlersForContentType(
                "com.adobe.pdf", CoreServices.kLSRolesAll
            )
            for bundle_identifier in bundle_identifiers:
                # Get the filesystem path of the app
                res = LaunchServices.LSCopyApplicationURLsForBundleIdentifier(
                    bundle_identifier, None
                )
                if res[0] is None:
                    continue
                app_url = res[0][0]
                app_path = str(app_url.path())

                # Load its plist file
                plist_path = os.path.join(app_path, "Contents/Info.plist")
                with open(plist_path, "rb") as f:
                    plist_data = f.read()
                plist_dict = plistlib.loads(plist_data)

                pdf_viewers[plist_dict["CFBundleName"]] = bundle_identifier

        elif platform.system() == "Linux":
            # Find all .desktop files
            for search_path in [
                "/usr/share/applications",
                "/usr/local/share/applications",
                os.path.expanduser("~/.local/share/applications"),
            ]:
                try:
                    for filename in os.listdir(search_path):
                        full_filename = os.path.join(search_path, filename)
                        if os.path.splitext(filename)[1] == ".desktop":

                            # See which ones can open PDFs
                            desktop_entry = DesktopEntry(full_filename)
                            if (
                                "application/pdf" in desktop_entry.getMimeTypes()
                                and desktop_entry.getName() != "dangerzone"
                            ):
                                pdf_viewers[
                                    desktop_entry.getName()
                                ] = desktop_entry.getExec()

                except FileNotFoundError:
                    pass

        return pdf_viewers
