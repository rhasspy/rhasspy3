"""Voice activity detection."""
from dataclasses import dataclass
from typing import Optional

from .event import Event, Eventable

DOMAIN = "vad"
_STARTED_TYPE = "voice-started"
_STOPPED_TYPE = "voice-stopped"


@dataclass
class VoiceStarted(Eventable):
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _STARTED_TYPE

    def event(self) -> Event:
        return Event(
            type=_STARTED_TYPE,
            data=None if self.timestamp is None else {"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "VoiceStarted":
        return VoiceStarted(
            timestamp=None if event.data is None else event.data.get("timestamp")
        )


@dataclass
class VoiceStopped(Eventable):
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _STOPPED_TYPE

    def event(self) -> Event:
        return Event(
            type=_STOPPED_TYPE,
            data=None if self.timestamp is None else {"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "VoiceStopped":
        return VoiceStopped(
            timestamp=None if event.data is None else event.data.get("timestamp")
        )
