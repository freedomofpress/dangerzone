class UpdaterError(Exception):
    pass


class ImageAlreadyUpToDate(UpdaterError):
    pass


class ImageNotFound(UpdaterError):
    pass


class SignatureError(UpdaterError):
    pass


class RegistryError(UpdaterError):
    pass


class InvalidMutliArchImage(RegistryError):
    """The queried image is not a multi-arch image"""

    pass


class ArchitectureNotFound(RegistryError):
    """The required architecture was not found in the
    provided manifest"""


class AirgappedImageDownloadError(UpdaterError):
    pass


class NoRemoteSignatures(SignatureError):
    pass


class SignatureVerificationError(SignatureError):
    pass


class SignatureExtractionError(SignatureError):
    pass


class SignaturesFolderDoesNotExist(SignatureError):
    pass


class InvalidSignatures(SignatureError):
    pass


class SignatureMismatch(SignatureError):
    pass


class LocalSignatureNotFound(SignatureError):
    pass


class CosignNotInstalledError(SignatureError):
    pass


class InvalidLogIndex(SignatureError):
    pass


class InvalidImageArchive(UpdaterError):
    """An invalid archive format was passed"""

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
