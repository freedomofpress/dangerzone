import pytest
import asyncio
from dangerzone.conversion.doc_to_pixels import DocumentToPixels, handle_index
from dangerzone.conversion.common import (
    FILETYPE_DOCUMENT,
    FILETYPE_IMAGE,
    FILETYPE_AUDIO,
    FILETYPE_VIDEO,
)
from unittest.mock import MagicMock, patch

@pytest.fixture
def converter():
    return DocumentToPixels()

def test_get_file_type(converter, mocker):
    mocker.patch.object(converter, "detect_mime_type", side_effect=[
        "application/pdf",
        "image/png",
        "audio/mpeg",
        "video/mp4",
        "text/plain",
    ])
    
    assert converter.get_file_type("file.pdf") == FILETYPE_DOCUMENT
    assert converter.get_file_type("file.png") == FILETYPE_IMAGE
    assert converter.get_file_type("file.mp3") == FILETYPE_AUDIO
    assert converter.get_file_type("file.mp4") == FILETYPE_VIDEO
    assert converter.get_file_type("file.txt") == FILETYPE_DOCUMENT

def test_handle_index_media(converter, mocker):
    # Mocking read_bytes to return some dummy data
    mocker.patch("dangerzone.conversion.doc_to_pixels.DocumentToPixels.read_bytes", return_value=b"dummy")
    # Mocking is_archive and is_email to return False (single file mode)
    mocker.patch("dangerzone.conversion.doc_to_pixels.is_archive", return_value=False)
    mocker.patch("dangerzone.conversion.doc_to_pixels.is_email", return_value=False)
    
    # Mocking write methods
    mock_write_int = mocker.patch("dangerzone.conversion.doc_to_pixels.DocumentToPixels.write_int")
    mock_write_bytes = mocker.patch("dangerzone.conversion.doc_to_pixels.DocumentToPixels.write_bytes")
    
    # Mocking converter.get_file_type
    mocker.patch.object(DocumentToPixels, "get_file_type", return_value=FILETYPE_VIDEO)
    
    with patch("builtins.open", mocker.mock_open()):
        asyncio.run(handle_index())
    
    # Expected: 
    # 1. write_int(1) -> num files
    # 2. write_uint8(FILETYPE_VIDEO) 
    # 3. write_int(len(path))
    # 4. write_bytes(path)
    
    mock_write_int.assert_any_call(1)
    # write_uint8 uses write_bytes(b"\x03") for FILETYPE_VIDEO
    mock_write_bytes.assert_any_call(b"\x03")
