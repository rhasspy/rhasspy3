"""Audio input/output."""
import audioop
import wave
from dataclasses import dataclass
from typing import Iterable, Optional

from .event import Event, Eventable

_TYPE = "audio-chunk"
_START_TYPE = "audio-start"
_STOP_TYPE = "audio-stop"

DEFAULT_IN_RATE = 16000  # Hz
DEFAULT_OUT_RATE = 22050  # Hz

DEFAULT_IN_WIDTH = 2  # bytes
DEFAULT_OUT_WIDTH = 2  # bytes

DEFAULT_IN_CHANNELS = 1  # mono
DEFAULT_OUT_CHANNELS = 1  # mono


@dataclass
class AudioChunk(Eventable):
    rate: int
    width: int
    channels: int
    audio: bytes
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _TYPE

    def event(self) -> Event:
        return Event(
            type=_TYPE,
            data={
                "rate": self.rate,
                "width": self.width,
                "channels": self.channels,
                "timestamp": self.timestamp,
            },
            payload=self.audio,
        )

    @staticmethod
    def from_event(event: Event) -> "AudioChunk":
        assert event.data is not None
        assert event.payload is not None

        return AudioChunk(
            rate=event.data["rate"],
            width=event.data["width"],
            channels=event.data["channels"],
            audio=event.payload,
            timestamp=event.data.get("timestamp"),
        )

    @property
    def samples(self) -> int:
        return len(self.audio) // (self.width * self.channels)

    @property
    def seconds(self) -> float:
        return self.samples / self.rate

    @property
    def milliseconds(self) -> int:
        return int(self.seconds * 1_000)


@dataclass
class AudioStart(Eventable):
    rate: int
    width: int
    channels: int
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _START_TYPE

    def event(self) -> Event:

        return Event(
            type=_START_TYPE,
            data={
                "rate": self.rate,
                "width": self.width,
                "channels": self.channels,
                "timestamp": self.timestamp,
            },
        )

    @staticmethod
    def from_event(event: Event) -> "AudioStart":
        assert event.data is not None
        return AudioStart(
            rate=event.data["rate"],
            width=event.data["width"],
            channels=event.data["channels"],
            timestamp=event.data.get("timestamp"),
        )


@dataclass
class AudioStop(Eventable):
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _STOP_TYPE

    def event(self) -> Event:
        return Event(
            type=_STOP_TYPE,
            data={"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "AudioStop":
        return AudioStop(timestamp=event.data.get("timestamp"))


@dataclass
class AudioChunkConverter:
    """Converts audio chunks using audioop."""

    rate: int
    width: int
    channels: int
    _ratecv_state = None

    def convert(self, chunk: AudioChunk) -> AudioChunk:
        if (
            (chunk.rate == self.rate)
            and (chunk.width == self.width)
            and (chunk.channels == self.channels)
        ):
            return chunk

        audio_bytes = chunk.audio

        if chunk.width != self.width:
            # Convert sample width
            audio_bytes = audioop.lin2lin(audio_bytes, chunk.width, self.width)

        if chunk.channels != self.channels:
            # Convert to mono or stereo
            if self.channels == 1:
                audio_bytes = audioop.tomono(audio_bytes, self.width, 1.0, 1.0)
            elif self.channels == 2:
                audio_bytes = audioop.tostereo(audio_bytes, self.width, 1.0, 1.0)
            else:
                raise ValueError(f"Cannot convert to channels: {self.channels}")

        if chunk.rate != self.rate:
            # Resample
            audio_bytes, self._ratecv_state = audioop.ratecv(
                audio_bytes,
                self.width,
                self.channels,
                chunk.rate,
                self.rate,
                self._ratecv_state,
            )

        return AudioChunk(
            self.rate, self.width, self.channels, audio_bytes, timestamp=chunk.timestamp
        )


def wav_to_chunks(
    wav_file: wave.Wave_read, samples_per_chunk: int, timestamp: int = 0
) -> Iterable[AudioChunk]:
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
