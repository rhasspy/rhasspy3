"""Audio input/output."""
import wave
from typing import Iterable

# pylint: disable=unused-import
from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop

DEFAULT_IN_RATE = 16000  # Hz
DEFAULT_OUT_RATE = 22050  # Hz

DEFAULT_IN_WIDTH = 2  # bytes
DEFAULT_OUT_WIDTH = 2  # bytes

DEFAULT_IN_CHANNELS = 1  # mono
DEFAULT_OUT_CHANNELS = 1  # mono

DEFAULT_SAMPLES_PER_CHUNK = 1024

__all__ = [
    "DEFAULT_IN_CHANNELS",
    "DEFAULT_IN_RATE",
    "DEFAULT_IN_WIDTH",
    "DEFAULT_OUT_CHANNELS",
    "DEFAULT_OUT_RATE",
    "DEFAULT_OUT_WIDTH",
    "DEFAULT_SAMPLES_PER_CHUNK",
    "AudioChunk",
    "AudioChunkConverter",
    "AudioStart",
    "AudioStop",
    "wav_to_chunks",
]


def wav_to_chunks(
    wav_file: wave.Wave_read, samples_per_chunk: int, timestamp: int = 0
) -> Iterable[AudioChunk]:
    """Splits WAV file into AudioChunks."""
    rate = wav_file.getframerate()
    width = wav_file.getsampwidth()
    channels = wav_file.getnchannels()
    audio_bytes = wav_file.readframes(samples_per_chunk)
    while audio_bytes:
        chunk = AudioChunk(
            rate=rate,
            width=width,
            channels=channels,
            audio=audio_bytes,
            timestamp=timestamp,
        )
        yield chunk
        timestamp += chunk.milliseconds
        audio_bytes = wav_file.readframes(samples_per_chunk)
