import hashlib
from typing import Any

import pytest
from pytest_mock import MockerFixture

from dangerzone.updater import errors
from dangerzone.updater.registry import (
    IMAGE_INDEX_MEDIA_TYPE,
    IMAGE_LIST_MEDIA_TYPE,
    Image,
    get_digest_for_arch,
    get_manifest,
    get_manifest_digest,
    parse_image_location,
    replace_image_digest,
)


def test_parse_image_location_no_tag() -> None:
    """Test that parse_image_location correctly handles an image location without a tag."""
    image_str = "ghcr.io/freedomofpress/dangerzone/v1"
    image = parse_image_location(image_str)

    assert isinstance(image, Image)
    assert image.registry == "ghcr.io"
    assert image.namespace == "freedomofpress"
    assert image.image_name == "dangerzone/v1"
    assert image.tag == "latest"  # Default tag should be "latest"
    assert image.digest is None


def test_parse_image_location_with_tag() -> None:
    """Test that parse_image_location correctly handles an image location with a tag."""
    image_str = "ghcr.io/freedomofpress/dangerzone/v1:v0.4.2"
    image = parse_image_location(image_str)

    assert isinstance(image, Image)
    assert image.registry == "ghcr.io"
    assert image.namespace == "freedomofpress"
    assert image.image_name == "dangerzone/v1"
    assert image.tag == "v0.4.2"


def test_parse_image_location_tag_plus_digest() -> None:
    """Test that parse_image_location handles an image location with a tag that includes a digest."""
    image_str = (
        "ghcr.io/freedomofpress/dangerzone/v1"
        ":20250205-0.8.0-148-ge67fbc1"
        "@sha256:19e8eacd75879d05f6621c2ea8dd955e68ee3e07b41b9d53f4c8cc9929a68a67"
    )

    image = parse_image_location(image_str)

    assert isinstance(image, Image)
    assert image.registry == "ghcr.io"
    assert image.namespace == "freedomofpress"
    assert image.image_name == "dangerzone/v1"
    assert image.tag == "20250205-0.8.0-148-ge67fbc1"
    assert (
        image.digest
        == "sha256:19e8eacd75879d05f6621c2ea8dd955e68ee3e07b41b9d53f4c8cc9929a68a67"
    )


def test_parse_invalid_image_location() -> None:
    """Test that parse_image_location raises an error for invalid image locations."""
    invalid_image_locations = [
        "ghcr.io/dangerzone",  # Missing namespace
        "ghcr.io/freedomofpress/dangerzone:",  # Empty tag
        "freedomofpress/dangerzone",  # Missing registry
        "ghcr.io:freedomofpress/dangerzone",  # Invalid format
        "",  # Empty string
    ]

    for invalid_image in invalid_image_locations:
        with pytest.raises(ValueError, match="Malformed image location"):
            parse_image_location(invalid_image)


def test_replace_image_digest() -> None:
    assert (
        replace_image_digest(
            "ghcr.io/freedomofpress/dangerzone-testing/v1@sha256:123456",
            "777777",
        )
        == "ghcr.io/freedomofpress/dangerzone-testing/v1@sha256:777777"
    )
    assert (
        replace_image_digest(
            "ghcr.io/freedomofpress/dangerzone-testing/v1:latest@sha256:123456",
            "777777",
        )
        == "ghcr.io/freedomofpress/dangerzone-testing/v1@sha256:777777"
    )


def test_get_manifest(mocker: MockerFixture) -> None:
    """Test that get_manifest correctly retrieves manifests from the registry."""
    image_str = "ghcr.io/freedomofpress/dangerzone:v0.4.2"

    # Mock the responses
    manifest_content = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
        "config": {
            "mediaType": "application/vnd.docker.container.image.v1+json",
            "size": 1234,
            "digest": "sha256:abc123def456",
        },
        "layers": [
            {
                "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": 12345,
                "digest": "sha256:layer1",
            }
        ],
    }

    mock_response_auth = mocker.Mock()
    mock_response_auth.json.return_value = {"token": "dummy_token"}
    mock_response_auth.raise_for_status.return_value = None

    mock_response_manifest = mocker.Mock()
    mock_response_manifest.json.return_value = manifest_content
    mock_response_manifest.status_code = 200
    mock_response_manifest.raise_for_status.return_value = None

    # Setup the mock to return different responses for each URL
    def mock_get(url: str, **kwargs: Any) -> Any:
        if "token" in url:
            return mock_response_auth
        else:
            return mock_response_manifest

    mocker.patch("requests.get", side_effect=mock_get)

    # Call the function
    response = get_manifest(image_str)

    # Verify the result
    assert response.status_code == 200
    assert response.json() == manifest_content


def _mock_multiarch_manifest(mocker: MockerFixture, media_type: str) -> None:
    manifest = {
        "schemaVersion": 2,
        "mediaType": media_type,
        "manifests": [
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:amd64digest",
                "platform": {"architecture": "amd64", "os": "linux"},
            },
            {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:arm64digest",
                "platform": {"architecture": "arm64", "os": "linux"},
            },
        ],
    }
    mock_response = mocker.Mock()
    mock_response.json.return_value = manifest
    mocker.patch("dangerzone.updater.registry.get_manifest", return_value=mock_response)


@pytest.mark.parametrize("media_type", [IMAGE_LIST_MEDIA_TYPE, IMAGE_INDEX_MEDIA_TYPE])
def test_get_digest_for_arch(mocker: MockerFixture, media_type: str) -> None:
    """Both Docker manifest lists and OCI image indexes are valid multi-arch images.

    BuildKit >= 0.31.0 pushes OCI image indexes by default, so we must accept
    them alongside the legacy Docker manifest list media type.
    """
    _mock_multiarch_manifest(mocker, media_type)

    assert get_digest_for_arch("ghcr.io/freedomofpress/dangerzone/v1", "amd64") == (
        "amd64digest"
    )
    assert get_digest_for_arch("ghcr.io/freedomofpress/dangerzone/v1", "arm64") == (
        "arm64digest"
    )


def test_get_digest_for_arch_not_multiarch(mocker: MockerFixture) -> None:
    """A single-arch image manifest is not a valid multi-arch image."""
    manifest = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
    }
    mock_response = mocker.Mock()
    mock_response.json.return_value = manifest
    mocker.patch("dangerzone.updater.registry.get_manifest", return_value=mock_response)

    with pytest.raises(errors.InvalidMultiArchImage):
        get_digest_for_arch("ghcr.io/freedomofpress/dangerzone/v1", "amd64")


def test_get_digest_for_arch_missing_arch(mocker: MockerFixture) -> None:
    _mock_multiarch_manifest(mocker, IMAGE_INDEX_MEDIA_TYPE)

    with pytest.raises(errors.ArchitectureNotFound):
        get_digest_for_arch("ghcr.io/freedomofpress/dangerzone/v1", "riscv64")


def test_get_manifest_digest() -> None:
    """Test that get_manifest_digest correctly calculates the manifest digest."""
    # Create a sample manifest content
    manifest_content = b'{"schemaVersion":2,"mediaType":"application/vnd.docker.distribution.manifest.v2+json"}'

    # Calculate the expected digest manually
    import hashlib

    expected_digest = hashlib.sha256(manifest_content).hexdigest()

    # Call the function with the content directly
    digest = get_manifest_digest("unused_image_str", manifest_content)

    # Verify the result
    assert digest == expected_digest


def test_get_manifest_digest_from_registry(mocker: MockerFixture) -> None:
    """Test that get_manifest_digest correctly retrieves and calculates digests from the registry."""
    image_str = "ghcr.io/freedomofpress/dangerzone:v0.4.2"

    # Sample manifest content
    manifest_content = b'{"schemaVersion":2,"mediaType":"application/vnd.docker.distribution.manifest.v2+json"}'
    expected_digest = hashlib.sha256(manifest_content).hexdigest()

    # Mock get_manifest
    mock_response = mocker.Mock()
    mock_response.content = manifest_content
    mocker.patch("dangerzone.updater.registry.get_manifest", return_value=mock_response)

    # Call the function
    digest = get_manifest_digest(image_str)

    # Verify the result
    assert digest == expected_digest
