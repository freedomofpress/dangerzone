import sys
import os
import inspect
import tempfile
import appdirs
from PyQt5 import QtGui
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
        self.pixel_dir = tempfile.TemporaryDirectory()
        self.safe_dir = tempfile.TemporaryDirectory()
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

        # Preload list of PDF viewers on computer
        self.pdf_viewers = self._find_pdf_viewers()

        # Languages supported by tesseract
        self.ocr_languages = {
            "Afrikaans": "ar",
            "Amharic": "amh",
            "Arabic": "ara",
            "Assamese": "asm",
            "Azerbaijani": "aze",
            "Azerbaijani (Cyrillic)": "aze_cyrl",
            "Belarusian": "bel",
            "Bengali": "ben",
            "Tibetan Standard": "bod",
            "Bosnian": "bos",
            "Breton": "bre",
            "Bulgarian": "bul",
            "Catalan": "cat",
            "Cebuano": "ceb",
            "Czech": "ces",
            "Chinese - Simplified": "chi_sim",
            "Chinese - Simplified (vertical)": "chi_sim_vert",
            "Chinese - Traditional": "chi_tra",
            "Chinese - Traditional (vertical)": "chi_tra_vert",
            "Cherokee": "chr",
            "Corsican": "cos",
            "Welsh": "cym",
            "Danish": "dan",
            "German": "deu",
            "Divehi": "div",
            "Dzongkha": "dzo",
            "Greek": "ell",
            "English": "eng",
            "English, Middle (1100-1500)": "enm",
            "Esperanto": "epo",
            "Estonian": "est",
            "Basque": "eus",
            "Faroese": "fao",
            "Persian": "fas",
            "Filipino": "fil",
            "Finnish": "fin",
            "French": "fra",
            "Frankish": "frk",
            "French, Middle (ca.1400-1600)": "frm",
            "Frisian (Western)": "fry",
            "Gaelic (Scots)": "gla",
            "Irish": "gle",
            "Galician": "glg",
            "Gujarati": "guj",
            "Hatian": "hat",
            "Hebrew": "heb",
            "Hindi": "hin",
            "Croatian": "hrv",
            "Hungarian": "hun",
            "Armenian": "hye",
            "Inuktitut": "iku",
            "Indonesian": "ind",
            "Icelandic": "isl",
            "Italian": "ita",
            "Italian - Old": "ita_old",
            "Javanese": "jav",
            "Japanese": "jpn",
            "Japanese (vertical)": "jpn_vert",
            "Kannada": "kan",
            "Georgian": "kat",
            "Old Georgian": "kat_old",
            "Kazakh": "kaz",
            "Khmer": "khm",
            "Kyrgyz": "kir",
            "Korean": "kor",
            "Korean (vertical)": "kor_vert",
            "Kurdish (Arabic)": "kur_ara",
            "Lao": "lao",
            "Latin": "lat",
            "Latvian": "lav",
            "Lithuanian": "lit",
            "Luxembourgish": "ltz",
            "Malayalam": "mal",
            "Marathi": "mar",
            "Macedonian": "mkd",
            "Maltese": "mlt",
            "Mongolian": "mon",
            "Maori": "mri",
            "Malay": "msa",
            "Burmese": "mya",
            "Nepali": "nep",
            "Dutch": "nld",
            "Norwegian": "nor",
            "Occitan (post 1500)": "oci",
            "Oriya": "ori",
            "script and orientation": "osd",
            "Punjabi": "pan",
            "Polish": "pol",
            "Portuguese": "por",
            "Pashto": "pus",
            "Quechua": "que",
            "Romanian": "ron",
            "Russian": "rus",
            "Sanskrit": "san",
            "Sinhala": "sin",
            "Slovakian": "slk",
            "Slovenian": "slv",
            "Sindhi": "snd",
            "Spanish": "spa",
            "Spanish, Castilian - Old": "spa_old",
            "Albanian": "sqi",
            "Serbian": "srp",
            "Serbian (Latin)": "srp_latn",
            "Sundanese": "sun",
            "Swahili": "swa",
            "Swedish": "swe",
            "Syriac": "syr",
            "Tamil": "tam",
            "Tatar": "tat",
            "Telugu": "tel",
            "Tajik": "tgk",
            "Thai": "tha",
            "Tigrinya": "tir",
            "Tonga": "ton",
            "Turkish": "tur",
            "Uyghur": "uig",
            "Ukrainian": "ukr",
            "Urdu": "urd",
            "Uzbek": "uzb",
            "Uzbek (Cyrillic)": "uzb_cyrl",
            "Vietnamese": "vie",
            "Yiddish": "yid",
            "Yoruba": "yor",
            "Arabic script": "Arabic",
            "Armenian script": "Armenian",
            "Bengali script": "Bengali",
            "Canadian Aboriginal script": "Canadian_Aboriginal",
            "Cherokee script": "Cherokee",
            "Cyrillic script": "Cyrillic",
            "Devanagari script": "Devanagari",
            "Ethiopic script": "Ethiopic",
            "Fraktur script": "Fraktur",
            "Georgian script": "Georgian",
            "Greek script": "Greek",
            "Gujarati script": "Gujarati",
            "Gurmukhi script": "Gurmukhi",
            "Han - Simplified script": "HanS",
            "Han - Simplified (vertical) script": "HanS_vert",
            "Han - Traditional script": "HanT",
            "Han - Traditional (vertical) script": "HanT_vert",
            "Hangul script": "Hangul",
            "Hangul (vertical) script": "Hangul_vert",
            "Hebrew script": "Hebrew",
            "Japanese script": "Japanese",
            "Japanese (vertical) script": "Japanese_vert",
            "Kannada script": "Kannada",
            "Khmer script": "Khmer",
            "Lao script": "Lao",
            "Latin script": "Latin",
            "Malayalam script": "Malayalam",
            "Myanmar script": "Myanmar",
            "Oriya (Odia) script": "Oriya",
            "Sinhala script": "Sinhala",
            "Syriac script": "Syriac",
            "Tamil script": "Tamil",
            "Telugu script": "Telugu",
            "Thaana script": "Thaana",
            "Thai script": "Thai",
            "Tibetan script": "Tibetan",
            "Vietnamese script": "Vietnamese",
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
            print("Error, can only run in dev mode so far")

        resource_path = os.path.join(prefix, filename)
        return resource_path

    def _find_pdf_viewers(self):
        pdf_viewers = {}

        for search_path in [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]:
            try:
                for filename in os.listdir(search_path):
                    full_filename = os.path.join(search_path, filename)
                    if os.path.splitext(filename)[1] == ".desktop":

                        desktop_entry = DesktopEntry(full_filename)
                        if "application/pdf" in desktop_entry.getMimeTypes():
                            pdf_viewers[
                                desktop_entry.getName()
                            ] = desktop_entry.getExec()

            except FileNotFoundError:
                pass

        return pdf_viewers
