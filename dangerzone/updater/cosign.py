import os
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..util import (
    get_resource_path,
    get_tails_socks_proxy,
    linux_system_is,
    subprocess_run,
)
from . import errors, log

"""
This module exposes functions to interact with the embedded cosign binary.
"""

_COSIGN_BINARY = str(get_resource_path("vendor/cosign").absolute())


def _cosign_run(
    cmd: list[str], disable_auth: bool = False, pin_rekor_key: bool = False
) -> subprocess.CompletedProcess:
    custom_env = {}
    if disable_auth:
        # Disable registry authentication by setting auth-related environment variables
        # to non-existent files.
        #
        # This prevents Podman/Docker from using any existing credentials that might be
        # configured on the system, avoiding potential authentication errors.
        log.debug("Disabling registry authentication for the 'cosign' command")
        custom_env["REGISTRY_AUTH_FILE"] = "does-not-exist"
        custom_env["DOCKER_CONFIG"] = "does-not-exist"
    if pin_rekor_key:
        # Pin the Rekor key, so that it's used in offline setups as well, or in case of
        # network hiccups. See:
        # https://github.com/freedomofpress/dangerzone/issues/1280
        rekor_pub_key = str(get_resource_path("rekor.pub"))
        log.debug(f"Pinning Rekor public key to {rekor_pub_key}")
        custom_env["SIGSTORE_REKOR_PUBLIC_KEY"] = rekor_pub_key
    if linux_system_is("Tails"):
        custom_env["HTTPS_PROXY"] = get_tails_socks_proxy()

    # NOTE: This is an uncommon way to update envvars. We basically want to ensure that
    # the environment variables we have set above will be passed to the command,
    # provided that they don't override the ones that the user has set.
    env = custom_env | os.environ.copy()

    cmd = [_COSIGN_BINARY] + cmd
    return subprocess_run(cmd, capture_output=True, check=True, env=env)


def verify_local_image(oci_image_folder: Path, pubkey: Path) -> None:
    """Verify the given path against the given public key"""
    try:
        _cosign_run(
            [
                "verify",
                "--key",
                str(pubkey),
                "--offline",
                "--local-image",
                str(oci_image_folder),
            ],
            disable_auth=True,
            pin_rekor_key=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.SignatureVerificationError(
            f"Failed to verify signature of local image: {e}"
        )


def verify_blob(pubkey: Path, bundle: str, payload: str) -> None:
    try:
        _cosign_run(
            [
                "verify-blob",
                "--offline",
                "--key",
                str(pubkey.absolute()),
                "--bundle",
                bundle,
                payload,
            ],
            disable_auth=True,
            pin_rekor_key=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.SignatureVerificationError(f"Failed to verify signature: {e}")
    log.debug("Verify blob: OK")


def download_signature(image: str, digest: str) -> list[str]:
    try:
        process = _cosign_run(
            ["download", "signature", f"{image}@sha256:{digest}"],
            disable_auth=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.NoRemoteSignatures(str(e))

    # Remove the last return, split on newlines, convert from JSON
    return process.stdout.decode("utf-8").strip().split("\n")


def save(arch_image: str, destination: Path) -> None:
    try:
        _cosign_run(
            ["save", arch_image, "--dir", str(destination.absolute())],
            disable_auth=True,
        )
    except subprocess.CalledProcessError as e:
        raise errors.AirgappedImageDownloadError()
