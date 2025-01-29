class UpdaterError(Exception):
    pass


class ImageAlreadyUpToDate(UpdaterError):
    pass


class SignatureError(UpdaterError):
    pass


class RegistryError(UpdaterError):
    pass


class NoRemoteSignatures(SignatureError):
    pass


class SignatureVerificationError(SignatureError):
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
