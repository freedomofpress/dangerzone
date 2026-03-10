import pytest
import os
import platform
import subprocess
import av
import fractions
import numpy as np
from dangerzone.isolation_provider.base import IsolationProvider
from dangerzone.document import Document
from dangerzone.conversion.common import INT_BYTES
from unittest.mock import MagicMock, patch

class MockProvider(IsolationProvider):
    def start_exec(self, document, command, stdin=subprocess.PIPE):
        # We need to return a mock process with stdout
        proc = MagicMock()
        proc.stdout = MagicMock()
        # Mock read_int (read 2 bytes)
        # width, height, fps
        proc.stdout.read.side_effect = [
            (640).to_bytes(2, "big"), # width
            (480).to_bytes(2, "big"), # height
            (30).to_bytes(2, "big"),  # fps
            b"" # EOF for subsequent reads
        ]
        proc.wait.return_value = 0
        return proc

    def start_doc_to_pixels_sandbox(self, document):
        pass
    def terminate_doc_to_pixels_sandbox(self, document, p):
        pass
    def get_max_parallel_conversions(self):
        return 1
    def requires_install(self):
        return False
    def print_progress(self, document, error, text, percentage):
        pass

def test_convert_video_pyav_encoding(mocker):
    # Mock Document.validate_input_filename to avoid FileNotFoundError
    mocker.patch("dangerzone.document.Document.validate_input_filename")

    # Generate dummy video frame data (640x480, RGB24, single frame of red)
    width, height, fps = 640, 480, 25
    video_frame_size = width * height * 3
    dummy_video_frame = b"\xff\x00\x00" * (width * height) # Red frame

    # Generate dummy audio data (1 second of s16le stereo silence at 48000 Hz)
    sample_rate = 48000 # Changed from 44100 to 48000
    channels = 2
    duration_seconds = 1
    
    # 3840 bytes corresponds to 960 s16le stereo samples (Opus compatible)
    audio_chunk_size_bytes = 3840
    num_samples_per_chunk = audio_chunk_size_bytes // (2 * channels) # s16le is 2 bytes, 2 channels
    
    # Create one frame of silent audio data
    dummy_audio_frame_data = (0).to_bytes(2, "little") * num_samples_per_chunk * channels
    
    # For a 1-second audio clip, generate multiple chunks
    # Note: The test will still feed 44.1kHz data, but the resampler will convert it.
    # The number of chunks should match the input data.
    original_sample_rate = 44100
    num_audio_chunks = (original_sample_rate * duration_seconds * channels * 2) // audio_chunk_size_bytes
    dummy_audio_chunks = [dummy_audio_frame_data] * num_audio_chunks


    # Mock the IsolationProvider to return mock processes with controlled stdout
    class MockProvider(IsolationProvider):
        def start_exec(self, document, command, stdin=subprocess.PIPE):
            proc = MagicMock()
            proc.stdout = MagicMock()
            if "--video-only" in command:
                proc.stdout.read.side_effect = (
                    [
                        width.to_bytes(INT_BYTES, "big"),
                        height.to_bytes(INT_BYTES, "big"),
                        fps.to_bytes(INT_BYTES, "big"),
                    ]
                    + ([dummy_video_frame] * (fps * duration_seconds))
                    + [b""]  # EOF
                )
            elif "--audio-only" in command:
                proc.stdout.read.side_effect = dummy_audio_chunks + [b""]
            proc.wait.return_value = 0
            return proc

        def start_doc_to_pixels_sandbox(self, document):
            pass
        def terminate_doc_to_pixels_sandbox(self, document, p):
            pass
        def get_max_parallel_conversions(self):
            return 1
        def requires_install(self):
            return False
        def print_progress(self, document, error, text, percentage):
            pass

    provider = MockProvider()
    doc = Document("test.mp4")

    # Create a temporary output file
    output_filepath = "test_output.webm"
    if os.path.exists(output_filepath):
        os.remove(output_filepath)

    try:
        provider._convert_video(doc, "test.mp4", output_filepath, 0, 1)

        # Verify output file exists and is a valid webm with expected streams
        assert os.path.exists(output_filepath)
        container = av.open(output_filepath)
        assert container.streams.video
        assert container.streams.audio
        assert container.streams.video[0].width == width
        assert container.streams.video[0].height == height
        assert container.streams.audio[0].rate == sample_rate
        assert container.streams.audio[0].channels == channels

    finally:
        if os.path.exists(output_filepath):
            os.remove(output_filepath)
