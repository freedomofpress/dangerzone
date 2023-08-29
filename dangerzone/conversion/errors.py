from typing import List, Optional, Type

# XXX: errors start at 128 for conversion-related issues
ERROR_SHIFT = 128
MAX_PAGES = 10000


class ConversionException(Exception):
    error_message = "Unspecified error"
    error_code = ERROR_SHIFT

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
    error_code = ERROR_SHIFT + 10
    error_message = "The document format is not supported"


class DocFormatUnsupportedHWPQubes(DocFormatUnsupported):
    error_code = ERROR_SHIFT + 16
    error_message = "HWP / HWPX formats are not supported in Qubes"


class LibreofficeFailure(ConversionException):
    error_code = ERROR_SHIFT + 20
    error_message = "Conversion to PDF with LibreOffice failed"


class InvalidGMConversion(ConversionException):
    error_code = ERROR_SHIFT + 30
    error_message = "Invalid conversion (Graphics Magic)"

    def __init__(self, error_message: str) -> None:
        super(error_message)


class PagesException(ConversionException):
    error_code = ERROR_SHIFT + 40


class NoPageCountException(PagesException):
    error_code = ERROR_SHIFT + 41
    error_message = "Number of pages could not be extracted from PDF"


class MaxPagesException(PagesException):
    """Max number of pages enforced by the client (to fail early) but also the
    server, which distrusts the client"""

    error_code = ERROR_SHIFT + 42
    error_message = f"Number of pages exceeds maximum ({MAX_PAGES})"


class PDFtoPPMException(ConversionException):
    error_code = ERROR_SHIFT + 50
    error_message = "Error converting PDF to Pixels (pdftoppm)"


class PDFtoPPMInvalidHeader(PDFtoPPMException):
    error_code = ERROR_SHIFT + 51
    error_message = "Error converting PDF to Pixels (Invalid PPM header)"


class PDFtoPPMInvalidDepth(PDFtoPPMException):
    error_code = ERROR_SHIFT + 52
    error_message = "Error converting PDF to Pixels (Invalid PPM depth)"


class InterruptedConversion(ConversionException):
    """Protocol received num of bytes different than expected"""

    error_code = ERROR_SHIFT + 60
    error_message = (
        "Something interrupted the conversion and it could not be completed."
    )


class UnexpectedConversionError(PDFtoPPMException):
    error_code = ERROR_SHIFT + 100
    error_message = "Some unexpected error occurred while converting the document"


def exception_from_error_code(error_code: int) -> Optional[ConversionException]:
    """returns the conversion exception corresponding to the error code"""
    for cls in ConversionException.get_subclasses():
        if cls.error_code == error_code:
            return cls()
    raise ValueError(f"Unknown error code '{error_code}'")
