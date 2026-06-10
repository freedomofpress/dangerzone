

class UpdaterError(Exception):
    """Base error class for all the updater errors"""

    def __init__(self, message: str | None = None, *args, **kwargs) -> None:  # type: ignore
        # Use the class docstring as the error message if none is given
        super().__init__(message or self.__doc__, *args, **kwargs)


class ImageAlreadyUpToDate(UpdaterError):
    """An upgrade was required but everything is already up to date"""



class ImageNotFound(UpdaterError):
    """
    A verification of the local container image was requested,
    but no image could be found
    """



class SignatureError(UpdaterError):
    """
    (Base class) An error was found while checking the signatures
    of the container image
    """



class RegistryError(UpdaterError):
    """(Base class) An error was found while interacting with the Container Registry"""



class InvalidMutliArchImage(RegistryError):
    """The queried image is not a multi-arch image"""



class ArchitectureNotFound(RegistryError):
    """The required architecture was not found in the
    provided manifest"""


class AirgappedImageDownloadError(UpdaterError):
    """Unable to download the container image using cosign download"""



class NoRemoteSignatures(SignatureError):
    """No remote signatures were found on the container registry"""



class SignatureVerificationError(SignatureError):
    """An error occured when checking the validity of the signatures"""



class SignatureExtractionError(SignatureError):
    """The signatures do not match the expected format"""



class SignaturesFolderDoesNotExist(SignatureError):
    """The signatures folder for the specific public key doesn't exist"""



class SignatureMismatch(SignatureError):
    """The signatures do not share the expected image digest"""



class LocalSignatureNotFound(SignatureError):
    """Unable to verify the local signatures as they cannot be found"""



class CosignNotInstalledError(SignatureError):
    """Cosign is not installed"""



class InvalidLogIndex(SignatureError):
    """The incoming log index is not greater than the previous one"""



class InvalidImageArchive(UpdaterError):
    """
    An invalid archive format was passed.

    Archives should contain a `dangerzone.json` file.
    The proper way to gather these archives is to use:

        dangerzone-image prepare-archive

    In your terminal.
    """



class InvalidDangerzoneManifest(InvalidImageArchive):
    """Raised when the dangerzone.json manifest does not match the index.json
    manifest in a container.tar image.

    This could mean that the container image has been tampered and is not safe
    to load, so we bail out.
    """



class NeedUserInput(UpdaterError):
    """The user has not yet been prompted to know if they want to check for updates."""



class NeedUserInputNoContainer(NeedUserInput):
    """The user must enable updates when no container image is available."""

