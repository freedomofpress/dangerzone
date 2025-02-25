import json
import unittest
from pathlib import Path

import pytest
from pytest_subprocess import FakeProcess

from dangerzone import errors as dzerrors
from dangerzone.updater import errors
from dangerzone.updater.signatures import (
    Signature,
    get_config_dir,
    get_last_log_index,
    get_log_index_from_signatures,
    get_remote_signatures,
    is_update_available,
    load_and_verify_signatures,
    prepare_airgapped_archive,
    store_signatures,
    upgrade_container_image,
    verify_local_image,
    verify_signature,
    verify_signatures,
)

ASSETS_PATH = Path(__file__).parent / "assets"
TEST_PUBKEY_PATH = ASSETS_PATH / "test.pub.key"
INVALID_SIGNATURES_PATH = ASSETS_PATH / "signatures" / "invalid"
VALID_SIGNATURES_PATH = ASSETS_PATH / "signatures" / "valid"
TEMPERED_SIGNATURES_PATH = ASSETS_PATH / "signatures" / "tempered"

RANDOM_DIGEST = "aacc9b586648bbe3040f2822153b1d5ead2779af45ff750fd6f04daf4a9f64b4"


@pytest.fixture
def valid_signature():
    signature_file = next(VALID_SIGNATURES_PATH.glob("**/*.json"))
    with open(signature_file, "r") as signature_file:
        signatures = json.load(signature_file)
        return signatures.pop()


@pytest.fixture
def signature_other_digest(valid_signature):
    signature = valid_signature.copy()
    signature["Bundle"]["Payload"]["digest"] = "sha256:123456"
    return signature
def tempered_signature():
    signature_file = next(TEMPERED_SIGNATURES_PATH.glob("**/*.json"))
    with open(signature_file, "r") as signature_file:
        signatures = json.load(signature_file)
        return signatures.pop()


@pytest.fixture


def test_load_valid_signatures(mocker):
    mocker.patch("dangerzone.updater.signatures.SIGNATURES_PATH", VALID_SIGNATURES_PATH)
    valid_signatures = list(VALID_SIGNATURES_PATH.glob("**/*.json"))
    assert len(valid_signatures) > 0
    for file in valid_signatures:
        signatures = load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)
        assert isinstance(signatures, list)
        assert len(signatures) > 0


def test_load_invalid_signatures(mocker):
    mocker.patch(
        "dangerzone.updater.signatures.SIGNATURES_PATH", INVALID_SIGNATURES_PATH
    )
    invalid_signatures = list(INVALID_SIGNATURES_PATH.glob("**/*.json"))
    assert len(invalid_signatures) > 0
    for file in invalid_signatures:
        with pytest.raises(errors.SignatureError):
            load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)


def test_load_tempered_signatures(mocker):
    mocker.patch(
        "dangerzone.updater.signatures.SIGNATURES_PATH", TEMPERED_SIGNATURES_PATH
    )
    tempered_signatures = list(TEMPERED_SIGNATURES_PATH.glob("**/*.json"))
    assert len(tempered_signatures) > 0
    for file in tempered_signatures:
        with pytest.raises(errors.SignatureError):
            load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)


def test_get_log_index_from_signatures():
    signatures = [{"Bundle": {"Payload": {"logIndex": 1}}}]
    assert get_log_index_from_signatures(signatures) == 1


def test_get_log_index_from_signatures_empty():
    signatures = []
    assert get_log_index_from_signatures(signatures) == 0


def test_get_log_index_from_malformed_signatures():
    signatures = [{"Bundle": {"Payload": {"logIndex": "foo"}}}]
    assert get_log_index_from_signatures(signatures) == 0


def test_get_log_index_from_missing_log_index():
    signatures = [{"Bundle": {"Payload": {}}}]
    assert get_log_index_from_signatures(signatures) == 0


def test_upgrade_container_image_if_already_up_to_date(mocker):
    mocker.patch(
        "dangerzone.updater.signatures.is_update_available", return_value=(False, None)
    )
    with pytest.raises(errors.ImageAlreadyUpToDate):
        upgrade_container_image(
            "ghcr.io/freedomofpress/dangerzone/dangerzone", "sha256:123456", "test.pub"
        )


def test_upgrade_container_without_signatures(mocker):
    mocker.patch(
        "dangerzone.updater.signatures.is_update_available",
        return_value=(True, "sha256:123456"),
    )
    mocker.patch("dangerzone.updater.signatures.get_remote_signatures", return_value=[])
    with pytest.raises(errors.SignatureVerificationError):
        upgrade_container_image(
            "ghcr.io/freedomofpress/dangerzone/dangerzone",
            "sha256:123456",
            "test.pub",
        )


def test_upgrade_container_lower_log_index(mocker):
    image_digest = "4da441235e84e93518778827a5c5745d532d7a4079886e1647924bee7ef1c14d"
    signatures = load_and_verify_signatures(
        image_digest,
        TEST_PUBKEY_PATH,
        bypass_verification=True,
        signatures_path=VALID_SIGNATURES_PATH,
    )
    mocker.patch(
        "dangerzone.updater.signatures.is_update_available",
        return_value=(
            True,
            image_digest,
        ),
    )
    mocker.patch(
        "dangerzone.updater.signatures.get_remote_signatures",
        return_value=signatures,
    )
    # Mock to avoid loosing time on test failures
    mocker.patch("dangerzone.container_utils.container_pull")
    # The log index of the incoming signatures is 168652066
    mocker.patch(
        "dangerzone.updater.signatures.get_last_log_index",
        return_value=168652067,
    )

    with pytest.raises(errors.InvalidLogIndex):
        upgrade_container_image(
            "ghcr.io/freedomofpress/dangerzone/dangerzone",
            image_digest,
            TEST_PUBKEY_PATH,
        )


def test_prepare_airgapped_archive_requires_digest():
    with pytest.raises(errors.AirgappedImageDownloadError):
        prepare_airgapped_archive(
            "ghcr.io/freedomofpress/dangerzone/dangerzone", "test.tar"
        )


def test_get_remote_signatures_error(fp: FakeProcess, mocker):
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"
    mocker.patch("dangerzone.updater.cosign.ensure_installed", return_value=True)
    fp.register_subprocess(
        ["cosign", "download", "signature", f"{image}@sha256:{digest}"], returncode=1
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_get_remote_signatures_empty(fp: FakeProcess, mocker):
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"
    mocker.patch("dangerzone.updater.cosign.ensure_installed", return_value=True)
    fp.register_subprocess(
        ["cosign", "download", "signature", f"{image}@sha256:{digest}"],
        stdout=json.dumps({}),
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_get_remote_signatures_cosign_error(mocker, fp: FakeProcess):
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"
    mocker.patch("dangerzone.updater.cosign.ensure_installed", return_value=True)
    fp.register_subprocess(
        ["cosign", "download", "signature", f"{image}@sha256:{digest}"],
        returncode=1,
        stderr="Error: no signatures associated",
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_store_signatures_with_different_digests(
    valid_signature, signature_other_digest
):
    signatures = [valid_signature, signature_other_digest]
    breakpoint()
    valid_signature, signature_other_digest, mocker, tmp_path

    """Test that store_signatures raises an error when a signature's digest doesn't match."""

    image_digest = "sha256:123456"

    # Mock the signatures path
    signatures_path = tmp_path / "signatures"
    signatures_path.mkdir()
    mocker.patch("dangerzone.updater.signatures.SIGNATURES_PATH", signatures_path)

    # Mock get_log_index_from_signatures
    mocker.patch(
        "dangerzone.updater.signatures.get_log_index_from_signatures",
        return_value=100,
    )

    # Mock get_last_log_index
    mocker.patch(
    # Call store_signatures
    with pytest.raises(errors.SignatureMismatch):
        store_signatures(signatures, image_digest, TEST_PUBKEY_PATH)
        "dangerzone.updater.signatures.get_last_log_index",
    # Verify that the signatures file was not created
    assert not (signatures_path / f"{image_digest}.json").exists()

    # Verify that the log index file was not updated
    assert not (signatures_path / "last_log_index").exists()

def test_stores_signatures_updates_last_log_index():
    pass


def test_get_file_digest():
    pass


def test_convert_oci_images_signatures():
    pass


def test_is_update_available_nothing_local():
    pass


def test_is_update_available_trims():
    pass


def test_verify_signature_wrong_payload_digest():
    pass


def test_verify_signatures_empty_list():
    with pytest.raises(errors.SignatureVerificationError):
        verify_signatures([], "1234", TEST_PUBKEY_PATH)
