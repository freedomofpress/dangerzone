import json
import unittest
from operator import attrgetter
from pathlib import Path
from typing import Any, Callable, Dict
from unittest.mock import patch

import pytest
from pytest_subprocess import FakeProcess

from dangerzone import errors as dzerrors
from dangerzone.updater import errors
from dangerzone.updater.cosign import _COSIGN_BINARY
from dangerzone.updater.signatures import (
    Signature,
    get_last_log_index,
    get_log_index_from_signatures,
    get_remote_digest_and_logindex,
    get_remote_signatures,
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
TAMPERED_SIGNATURES_PATH = ASSETS_PATH / "signatures" / "tampered"

RANDOM_DIGEST = "aacc9b586648bbe3040f2822153b1d5ead2779af45ff750fd6f04daf4a9f64b4"


@pytest.fixture
def valid_signature() -> Dict[str, Any]:
    # Use next() as we don't really care which signature we get.
    signature_file_path = next(VALID_SIGNATURES_PATH.glob("**/*.json"))
    with open(signature_file_path, "r") as signature_file:
        signatures = json.load(signature_file)
        return signatures.pop()


@pytest.fixture
def tampered_signature() -> Dict[str, Any]:
    signature_file_path = next(TAMPERED_SIGNATURES_PATH.glob("**/*.json"))
    with open(signature_file_path, "r") as signature_file:
        signatures = json.load(signature_file)
        return signatures.pop()


@pytest.fixture
def signature_other_digest(valid_signature: Dict[str, Any]) -> Dict[str, Any]:
    signature = valid_signature.copy()
    signature["Bundle"]["Payload"]["digest"] = "sha256:123456"
    return signature


def for_each_signature(path: Path):  # type: ignore
    """
    Decorator that patches the signature path
    and parametrize pytest to run for each of the files within the given path
    """

    def wrapped(func: Callable):  # type: ignore
        patched_func = patch("dangerzone.updater.signatures.SIGNATURES_PATH", path)(
            func
        )
        files = list(path.glob("**/*.json"))
        return pytest.mark.parametrize(
            "file", files, ids=map(attrgetter("name"), files)
        )(patched_func)

    return wrapped


@for_each_signature(VALID_SIGNATURES_PATH)
def test_load_valid_signatures(file: Path) -> None:
    signatures = load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)
    assert isinstance(signatures, list)
    assert len(signatures) > 0


@for_each_signature(INVALID_SIGNATURES_PATH)
def test_load_invalid_signatures(file: Path) -> None:
    with pytest.raises(errors.SignatureError):
        load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)


@for_each_signature(TAMPERED_SIGNATURES_PATH)
def test_load_tampered_signatures(file: Path) -> None:
    with pytest.raises(errors.SignatureError):
        load_and_verify_signatures(file.stem, TEST_PUBKEY_PATH)


def test_get_log_index_from_signatures() -> None:
    signatures = [{"Bundle": {"Payload": {"logIndex": 1}}}]
    assert get_log_index_from_signatures(signatures) == 1


def test_get_log_index_from_signatures_empty() -> None:
    signatures: list[Dict[str, Any]] = []
    assert get_log_index_from_signatures(signatures) == 0


def test_get_log_index_from_malformed_signatures() -> None:
    signatures: list[Dict[str, Any]] = [{"Bundle": {"Payload": {"logIndex": "foo"}}}]
    assert get_log_index_from_signatures(signatures) == 0


def test_get_log_index_from_missing_log_index() -> None:
    signatures: list[Dict[str, Any]] = [{"Bundle": {"Payload": {}}}]
    assert get_log_index_from_signatures(signatures) == 0


def test_upgrade_container_without_signatures(mocker: Any) -> None:
    # Need to patch here, because if we pass signatures=[]
    # it will be considered empty and trigger a download anyway ([] is Falsey)
    mocker.patch("dangerzone.updater.signatures.get_remote_signatures", return_value=[])
    with pytest.raises(errors.SignatureVerificationError):
        upgrade_container_image(
            "sha256:123456",
            "ghcr.io/freedomofpress/dangerzone/dangerzone",
            TEST_PUBKEY_PATH,
        )


def test_upgrade_container_lower_log_index(mocker: Any) -> None:
    image_digest = "4da441235e84e93518778827a5c5745d532d7a4079886e1647924bee7ef1c14d"
    signatures = load_and_verify_signatures(
        image_digest,
        TEST_PUBKEY_PATH,
        bypass_verification=True,
        signatures_path=VALID_SIGNATURES_PATH,
    )

    # Mock to avoid losing time on test failures
    mocker.patch("dangerzone.container_utils.container_pull")
    # The log index of the incoming signatures is 168652066
    mocker.patch(
        "dangerzone.updater.signatures.get_last_log_index",
        return_value=168652067,
    )

    with pytest.raises(errors.InvalidLogIndex):
        upgrade_container_image(
            image_digest,
            "ghcr.io/freedomofpress/dangerzone/dangerzone",
            TEST_PUBKEY_PATH,
            signatures=signatures,
        )

    # And it should go trough if we ask to bypass the logindex checks
    upgrade_container_image(
        image_digest,
        "ghcr.io/freedomofpress/dangerzone/dangerzone",
        TEST_PUBKEY_PATH,
        bypass_logindex_check=True,
        signatures=signatures,
    )


def test_get_remote_signatures_error(fp: FakeProcess, mocker: Any) -> None:
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"
    fp.register_subprocess(
        [_COSIGN_BINARY, "download", "signature", f"{image}@sha256:{digest}"],
        returncode=1,
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_get_remote_signatures_empty(fp: FakeProcess, mocker: Any) -> None:
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"
    fp.register_subprocess(
        [_COSIGN_BINARY, "download", "signature", f"{image}@sha256:{digest}"],
        stdout=json.dumps({}),
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_get_remote_signatures_cosign_error(mocker: Any, fp: FakeProcess) -> None:
    image = "ghcr.io/freedomofpress/dangerzone/dangerzone"
    digest = "123456"

    fp.register_subprocess(
        [_COSIGN_BINARY, "download", "signature", f"{image}@sha256:{digest}"],
        returncode=1,
        stderr="Error: no signatures associated",
    )
    with pytest.raises(errors.NoRemoteSignatures):
        get_remote_signatures(image, digest)


def test_store_signatures_with_different_digests(
    valid_signature: Dict[str, Any],
    signature_other_digest: Dict[str, Any],
    mocker: Any,
    tmp_path: Any,
) -> None:
    """Test that store_signatures raises an error when a signature's digest doesn't match."""
    signatures = [valid_signature, signature_other_digest]
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
        "dangerzone.updater.signatures.get_last_log_index",
        return_value=50,
    )

    # Call store_signatures
    with pytest.raises(errors.SignatureMismatch):
        store_signatures(signatures, image_digest, TEST_PUBKEY_PATH)

    # Verify that the signatures file was not created
    assert not (signatures_path / f"{image_digest}.json").exists()

    # Verify that the log index file was not created
    assert not (signatures_path / "last_log_index").exists()


def test_stores_signatures_updates_last_log_index(
    valid_signature: Dict[str, Any], mocker: Any, tmp_path: Any
) -> None:
    """Test that store_signatures updates the last log index file."""
    signatures = [valid_signature]
    # Extract the digest from the signature
    image_digest = Signature(valid_signature).manifest_digest

    # Mock the signatures path
    signatures_path = tmp_path / "signatures"
    signatures_path.mkdir()
    mocker.patch("dangerzone.updater.signatures.SIGNATURES_PATH", signatures_path)

    # Create an existing last_log_index file with a lower value
    with open(signatures_path / "last_log_index", "w") as f:
        f.write("50")

    # Mock get_log_index_from_signatures to return a higher value
    mocker.patch(
        "dangerzone.updater.signatures.get_log_index_from_signatures",
        return_value=100,
    )

    # Call store_signatures
    store_signatures(signatures, image_digest, TEST_PUBKEY_PATH)

    # Verify that the log index file was updated
    assert (signatures_path / "last_log_index").exists()
    with open(signatures_path / "last_log_index", "r") as f:
        assert f.read() == "100"


def test_get_remote_digest_and_logindex_when_remote_image_available(
    mocker: Any, valid_signature: Dict[str, Any]
) -> None:
    """
    Test that is_update_available returns True when a new image is available
    and all checks pass
    """
    signature = Signature(valid_signature)
    # Mock is_new_remote_image_available to return True and digest
    mocker.patch(
        "dangerzone.updater.registry.get_manifest_digest",
        return_value=signature.manifest_digest,
    )
    mocker.patch(
        "dangerzone.updater.signatures.get_remote_signatures",
        return_value=[signature.signature],
    )

    # Call is_update_available
    digest, log_index, signatures = get_remote_digest_and_logindex(
        "ghcr.io/freedomofpress/dangerzone",
        TEST_PUBKEY_PATH,
    )

    # Verify the result
    assert digest == signature.manifest_digest
    assert log_index == signature.log_index


def test_verify_signature(valid_signature: Dict[str, Any]) -> None:
    """Test that verify_signature raises an error when the payload digest doesn't match."""
    verify_signature(
        valid_signature,
        Signature(valid_signature).manifest_digest,
        TEST_PUBKEY_PATH,
    )


def test_verify_signature_tampered(tampered_signature: Dict[str, Any]) -> None:
    """Test that verify_signature raises an error when the payload digest doesn't match."""
    # Call verify_signature and expect an error
    with pytest.raises(errors.SignatureError):
        verify_signature(
            tampered_signature,
            Signature(tampered_signature).manifest_digest,
            TEST_PUBKEY_PATH,
        )


def test_verify_signatures_empty_list() -> None:
    with pytest.raises(errors.SignatureVerificationError):
        verify_signatures([], "1234", TEST_PUBKEY_PATH)


def test_verify_signatures_not_0() -> None:
    pass
