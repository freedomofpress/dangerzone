from typing import Callable, Optional

from signatures import (
    BUNDLED_LOG_INDEX,
    LAST_LOG_INDEX,
    get_last_log_index,
    get_remote_log_index,
    install_local_container_tar,
    is_update_available,
    upgrade_container_image,
)

from .. import container_utils as runtime
from .. import log
from ..settings import Settings
from . import registry, signatures


def install(callback: Optional[Callable] = None):
    """
    Check if there is a need to update the Dangerzone container image,
    taking into account the user preference, the installed container images
    and the released container images if updates are enabled.

    In case an update needs to be applied, apply it.
    """
    # The logic to decide what to install is comparing the following
    # indexes:
    #
    # local_log_index:
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
    if not settings.get("update_check_all"):
        log.debug("Skipping remote container upgrade (applying user settings)")
        remote_log_index = 0
    else:
        remote_log_index = signatures.get_remote_log_index(container_name) or 0

    # Get the greatest log index, and store it as our target number
    max_log_index = max(local_log_index, remote_log_index, BUNDLED_LOG_INDEX)
    log.debug(f"local_log_index={local_log_index}")
    log.debug(f"remote_log_index={remote_log_index}")
    log.debug(f"bundled_log_index={BUNDLED_LOG_INDEX}")
    log.debug(f"max_log_index={max_log_index}")

    if local_log_index == max_log_index:
        # The application is either up-to-date, has disabled upgrades, or has downgraded.
        # Matching scenarios: 6, 7, 8, 10 (already installed by CLI), 12 (already installed by CLI)
        log.debug("Don't need to upgrade the container image")
        return
    elif bundled_log_index == max_log_index:
        # The bundled container image is fresher than the installed version,
        # or just as fresh as the remote one.
        # Matching scenarios: 1, 2, 3, 9a (if log indexes are the same), 9b, 11 (if no remote updates)
        log.debug("Install the bundled container image")
        install_local_container_tar()
    else:
        # There is a remote update that is fresher than the currently installed/available tarball
        #
        # Matching scenarios: 5, 9a, 11 (if more recent remote updates)
        log.debug("Install remote container update")
        _, image_digest = is_update_available(container_name)
        upgrade_container_image(image_digest, callback=callback)
        verify_local_image()
        runtime.clear_old_images(digest_to_keep=image_digest)
