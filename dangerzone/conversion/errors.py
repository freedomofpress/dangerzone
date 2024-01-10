from typing import List, Optional, Type, Union

# XXX: errors start at 128 for conversion-related issues
ERROR_SHIFT = 128
MAX_PAGES = 10000
MAX_PAGE_WIDTH = 10000
MAX_PAGE_HEIGHT = 10000


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


class QubesQrexecFailed(ConversionException):
    error_code = 126  # No ERROR_SHIFT since this is a qrexec error
    error_message = (
        "Could not start a disposable qube for the file conversion. "
        "More information should have shown up on the top-right corner of your screen."
    )


class DocFormatUnsupported(ConversionException):
    error_code = ERROR_SHIFT + 10
    error_message = "The document format is not supported"


class DocFormatUnsupportedHWPQubes(DocFormatUnsupported):
    error_code = ERROR_SHIFT + 16
    error_message = "HWP / HWPX formats are not supported in Qubes"


class LibreofficeFailure(ConversionException):
    error_code = ERROR_SHIFT + 20
    error_message = "Conversion to PDF with LibreOffice failed"


class DocCorruptedException(ConversionException):
    error_code = ERROR_SHIFT + 30
    error_message = "The document appears to be corrupted and could not be opened"


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


class MaxPageWidthException(PagesException):
    error_code = ERROR_SHIFT + 44
    error_message = f"A page exceeded the maximum width."


class MaxPageHeightException(PagesException):
    error_code = ERROR_SHIFT + 45
    error_message = f"A page exceeded the maximum height."


class PageCountMismatch(PagesException):
    error_code = ERROR_SHIFT + 46
    error_message = (
        "The final document does not have the same page count as the original one"
    )


class ConverterProcException(ConversionException):
    """Some exception occurred in the converter"""

    error_code = ERROR_SHIFT + 60
    error_message = (
        "Something interrupted the conversion and it could not be completed."
    )


class UnexpectedConversionError(ConversionException):
    error_code = ERROR_SHIFT + 100
    error_message = "Some unexpected error occurred while converting the document"


def exception_from_error_code(
    error_code: int,
) -> Union[ConversionException, ValueError]:
    """returns the conversion exception corresponding to the error code"""
    for cls in ConversionException.get_subclasses():
        if cls.error_code == error_code:
            return cls()
    raise ValueError(f"Unknown error code '{error_code}'")
