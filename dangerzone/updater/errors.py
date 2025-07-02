from typing import Optional


class UpdaterError(Exception):
    """Base error class for all the updater errors"""

    def __init__(self, message: Optional[str] = None, *args, **kwargs) -> None:  # type: ignore
        # Use the class docstring as the error message if none is given
        super().__init__(message or self.__doc__, *args, **kwargs)


class ImageAlreadyUpToDate(UpdaterError):
    """An upgrade was required but everything is already up to date"""

    pass


class ImageNotFound(UpdaterError):
    """
    A verification of the local container image was requested,
    but no image could be found
    """

    pass


class SignatureError(UpdaterError):
    """
    (Base class) An error was found while checking the signatures
    of the container image
    """

    pass


class RegistryError(UpdaterError):
    """(Base class) An error was found while interacting with the Container Registry"""

    pass


class InvalidMutliArchImage(RegistryError):
    """The queried image is not a multi-arch image"""

    pass


class ArchitectureNotFound(RegistryError):
    """The required architecture was not found in the
    provided manifest"""


class AirgappedImageDownloadError(UpdaterError):
    """Unable to download the container image using cosign download"""

    pass


class NoRemoteSignatures(SignatureError):
    """No remote signatures were found on the container registry"""

    pass


class SignatureVerificationError(SignatureError):
    """An error occured when checking the validity of the signatures"""

    pass


class SignatureExtractionError(SignatureError):
    """The signatures do not match the expected format"""

    pass


class SignaturesFolderDoesNotExist(SignatureError):
    """The signatures folder for the specific public key doesn't exist"""

    pass


class SignatureMismatch(SignatureError):
    """The signatures do not share the expected image digest"""

    pass


class LocalSignatureNotFound(SignatureError):
    """Unable to verify the local signatures as they cannot be found"""

    pass


class CosignNotInstalledError(SignatureError):
    """Cosign is not installed"""

    pass


class InvalidLogIndex(SignatureError):
    """The incoming log index is not greater than the previous one"""

    pass


class InvalidImageArchive(UpdaterError):
    """
    An invalid archive format was passed.

    Archives should contain a `dangerzone.json` file.
    The proper way to gather these archives is to use:

        dangerzone-image prepare-archive

    In your terminal.
    """

    pass


class InvalidDangerzoneManifest(InvalidImageArchive):
    """Raised when the dangerzone.json manifest does not match the index.json
    manifest in a container.tar image.

    This could mean that the container image has been tampered and is not safe
    to load, so we bail out.
    """

    pass


class NeedUserInput(UpdaterError):
    """The user has not yet been prompted to know if they want to check for updates."""

    pass
