import logging
from enum import Enum
from logging import Handler, LogRecord
from typing import Callable, Optional

from .. import container_utils as runtime
from ..settings import Settings
from . import log as updater_log
from . import registry, signatures
from .signatures import (
    BUNDLED_LOG_INDEX,
    LAST_LOG_INDEX,
    get_last_log_index,
    get_remote_digest_and_logindex,
    install_local_container_tar,
    upgrade_container_image,
    verify_local_image,
)

log = logging.getLogger(__name__)


class CallbackHandler(Handler):
    """
    A Logging handler that copies INFO log records
    to a specified callback.

    The main use-case being to display the progress
    to the user.
    """

    def __init__(self, callback: Optional[Callable]) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: LogRecord) -> None:
        if record.levelname == "INFO" and self.callback:
            self.callback(f"{record.getMessage()}\n")


class Strategy(Enum):
    DO_NOTHING = 1
    INSTALL_LOCAL_CONTAINER = 2
    INSTALL_REMOTE_CONTAINER = 3


def apply_installation_strategy(
    strategy: Strategy, callback: Optional[Callable] = None
) -> None:
    """
    Install or upgrade a container registry, based on previous computations.
    """
    if strategy == Strategy.DO_NOTHING:
        return
    elif strategy == Strategy.INSTALL_LOCAL_CONTAINER:
        log.debug("Install the local container tarball")
        install_local_container_tar()
        verify_local_image()
    elif strategy == Strategy.INSTALL_REMOTE_CONTAINER:
        log.debug("Download and install a remote container image")
        container_name = runtime.expected_image_name()

        # Also copy the logs INFO to the user interface
        updater_log.addHandler(CallbackHandler(callback))

        remote_digest, remote_log_index, signatures = get_remote_digest_and_logindex(
            container_name
        )
        upgrade_container_image(remote_digest, callback=callback, signatures=signatures)
        verify_local_image()
        runtime.clear_old_images(digest_to_keep=remote_digest)


def get_installation_strategy() -> Strategy:
    """
    Check if there is a need to update the Dangerzone container image,
    taking into account the user preference, the installed container images
    and the released container images if updates are enabled.
    """
    # The logic to decide what to install is comparing the following
    # indexes:
    #
    # local_log_index:get_remote_digest_and_logindex
    #
    #   The largest log index of any installed container image.
    #
    #   If an image is not present or this information is missing,
    #   treat it as 0, meaning that a container image needs to be installed
    #   either locally or remotely.
    #
    #   Because it's read from the signatures, it can be greater than
    #   the log index of the actual installed image, in case of downgrades.
    #
    # remote_log_index:
    # BUNDLED_LOG_INDEX,
    #   The largest log index for remote updates.
    #
    #   This log index and the corresponding signatures have been verified
    #   by the application before.
    #
    #   If updates are disabled, or errors occured while attempting to detect
    #   updates, it is treated as 0 for this run, meaning that we should not
    #   install images remotely.
    #
    #   If the update checker cannot run right away, it will use the latest
    #   value that it has observed.
    #
    # BUNDLED_LOG_INDEX:
    #
    #   The log index of the image bundled with dangerzone.
    #   It remains the same during the lifetime of a released Dangerzone
    #   version, and it can never be None/0.
    #
    # max_log_index:
    #
    #   The target log index for this run, calculated as
    #   the max of all the above indexes.

    podman_images = runtime.list_image_digests()
    settings = Settings()
    container_name = runtime.expected_image_name()

    # Compute the local log index
    if not podman_images or not LAST_LOG_INDEX.exists():
        log.debug("No podman images or no last_log_index file")
        local_log_index = 0
    else:
        # FIXME: pass container_name to get_last_log_index() to avoid
        # situations where the image name changed.
        local_log_index = get_last_log_index()

    # Compute the remote log index
    if not settings.get("updater_check_all"):
        log.debug("Skipping remote container upgrade (applying user settings)")
        remote_log_index = 0
    else:
        remote_log_index = settings.get("updater_remote_log_index")

    # Get the greatest log index, and store it as our target number
    max_log_index = max(local_log_index, remote_log_index, BUNDLED_LOG_INDEX)
    log.debug(f"local_log_index={local_log_index}")
    log.debug(f"remote_log_index={remote_log_index}")
    log.debug(f"bundled_log_index={BUNDLED_LOG_INDEX}")
    log.debug(f"max_log_index={max_log_index}")

    if local_log_index == max_log_index:
        # The application is either up-to-date, has disabled upgrades, or has downgraded.
        # Matching scenarios: 6, 7, 8, 10 (already installed by CLI), 12 (already installed by CLI)
        log.debug("Installation strategy: Do nothing")
        return Strategy.DO_NOTHING
    elif BUNDLED_LOG_INDEX == max_log_index:
        # The bundled container image is fresher than the installed version,
        # or just as fresh as the remote one.
        # Matching scenarios: 1, 2, 3, 9a (if log indexes are the same), 9b, 11 (if no remote updates)
        log.debug("Installation strategy: Install the local container")
        return Strategy.INSTALL_LOCAL_CONTAINER
    else:
        # There is a remote update that is fresher than the currently installed/available tarball
        #
        # Matching scenarios: 5, 9a, 11 (if more recent remote updates)
        log.debug("Installation strategy: Remote container update")
        return Strategy.INSTALL_REMOTE_CONTAINER
