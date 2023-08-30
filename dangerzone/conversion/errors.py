from typing import List, Optional, Type


class ConversionException(Exception):
    error_message = "Unspecified error"
    error_code = -1

    def __init__(self, error_message: Optional[str] = None) -> None:
        if error_message:
            self.error_message = error_message
        super().__init__(self.error_message)

    @classmethod
    def get_subclasses(cls) -> List[Type["ConversionException"]]:
        subclasses = [cls]
        for subclass in cls.__subclasses__():
            subclasses += subclass.get_subclasses()
        return subclasses


class DocFormatUnsupported(ConversionException):
    error_code = 10
    error_message = "The document format is not supported"


class DocFormatUnsupportedHWPQubes(DocFormatUnsupported):
    error_code = 16
    error_message = "HWP / HWPX formats are not supported in Qubes"


class LibreofficeFailure(ConversionException):
    error_code = 20
    error_message = "Conversion to PDF with LibreOffice failed"


class InvalidGMConversion(ConversionException):
    error_code = 30
    error_message = "Invalid conversion (Graphics Magic)"

    def __init__(self, error_message: str) -> None:
        super(error_message)


class PagesException(ConversionException):
    error_code = 40


class NoPageCountException(PagesException):
    error_code = 41
    error_message = "Number of pages could not be extracted from PDF"


class PDFtoPPMException(ConversionException):
    error_code = 50
    error_message = "Error converting PDF to Pixels (pdftoppm)"


class PDFtoPPMInvalidHeader(PDFtoPPMException):
    error_code = 51
    error_message = "Error converting PDF to Pixels (Invalid PPM header)"


class PDFtoPPMInvalidDepth(PDFtoPPMException):
    error_code = 52
    error_message = "Error converting PDF to Pixels (Invalid PPM depth)"


def exception_from_error_code(error_code: int) -> Optional[ConversionException]:
    """returns the conversion exception corresponding to the error code"""
    for cls in ConversionException.get_subclasses():
        if cls.error_code == error_code:
            return cls()
    raise ValueError(f"Unknown error code '{error_code}'")
