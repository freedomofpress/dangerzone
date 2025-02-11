class UpdaterError(Exception):
    pass


class ImageNotFound(UpdaterError):
    pass


class RegistryError(UpdaterError):
    pass
