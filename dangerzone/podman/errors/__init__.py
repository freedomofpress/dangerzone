"""Podman API errors Package.

Import exceptions from 'importlib' are used to differentiate between APIConnection
and PodmanClient errors. Therefore, installing both APIConnection and PodmanClient
is not supported. PodmanClient related errors take precedence over APIConnection ones.

ApiConnection and associated classes have been deprecated.
"""

import warnings
from http.client import HTTPException

# isort: unique-list
__all__ = [
    "APIError",
    "CommandError",
    "BuildError",
    "ContainerError",
    "DockerException",
    "ImageNotFound",
    "InvalidArgument",
    "NotFound",
    "NotFoundError",
    "PodmanError",
    "PodmanNotInstalled",
    "ServiceTerminatedServiceTimeout",
    "StreamParseError",
]

try:
    from .exceptions import (
        APIError,
        BuildError,
        CommandError,
        ContainerError,
        DockerException,
        InvalidArgument,
        NotFound,
        PodmanError,
        PodmanNotInstalled,
        ServiceTerminated,
        ServiceTimeout,
        StreamParseError,
    )
except ImportError:
    pass


class NotFoundError(HTTPException):
    """HTTP request returned a http.HTTPStatus.NOT_FOUND.

    Deprecated.
    """

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response
        warnings.warn(
            "APIConnection() and supporting classes.",
            PendingDeprecationWarning,
            stacklevel=2,
        )


# If found, use new ImageNotFound otherwise old class
try:
    from .exceptions import ImageNotFound
except ImportError:

    class ImageNotFound(NotFoundError):  # type: ignore[no-redef]
        """HTTP request returned a http.HTTPStatus.NOT_FOUND.

        Specialized for Image not found. Deprecated.
        """


class NetworkNotFound(NotFoundError):
    """Network request returned a http.HTTPStatus.NOT_FOUND.

    Deprecated.
    """


class ContainerNotFound(NotFoundError):
    """HTTP request returned a http.HTTPStatus.NOT_FOUND.

    Specialized for Container not found. Deprecated.
    """


class PodNotFound(NotFoundError):
    """HTTP request returned a http.HTTPStatus.NOT_FOUND.

    Specialized for Pod not found. Deprecated.
    """


class ManifestNotFound(NotFoundError):
    """HTTP request returned a http.HTTPStatus.NOT_FOUND.

    Specialized for Manifest not found. Deprecated.
    """


class RequestError(HTTPException):
    """Podman service reported issue with the request.

    Deprecated.
    """

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response
        warnings.warn(
            "APIConnection() and supporting classes.",
            PendingDeprecationWarning,
            stacklevel=2,
        )


class InternalServerError(HTTPException):
    """Podman service reported an internal error.

    Deprecated.
    """

    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response
        warnings.warn(
            "APIConnection() and supporting classes.",
            PendingDeprecationWarning,
            stacklevel=2,
        )
