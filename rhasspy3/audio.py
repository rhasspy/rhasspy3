"""Audio input/output."""
from dataclasses import dataclass
from typing import Optional

from .event import Event, Eventable

_TYPE = "audio-chunk"
_START_TYPE = "audio-start"
_STOP_TYPE = "audio-stop"


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
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _START_TYPE

    def event(self) -> Event:
        return Event(
            type=_START_TYPE,
            data=None if self.timestamp is None else {"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "AudioStart":
        return AudioStart(
            timestamp=None if event.data is None else event.data.get("timestamp")
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
            data=None if self.timestamp is None else {"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "AudioStop":
        return AudioStop(
            timestamp=None if event.data is None else event.data.get("timestamp")
        )
