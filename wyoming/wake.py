"""Wake word detection"""
from dataclasses import dataclass
from typing import Optional

from .event import Event, Eventable

DOMAIN = "wake"
_DETECTION_TYPE = "detection"
_NOT_DETECTED_TYPE = "not-detected"


@dataclass
class Detection(Eventable):
    """Wake word was detected."""

    name: Optional[str] = None
    """Name of model."""

    timestamp: Optional[int] = None
    """Timestamp of audio chunk with detection"""

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _DETECTION_TYPE

    def event(self) -> Event:
        return Event(
            type=_DETECTION_TYPE, data={"name": self.name, "timestamp": self.timestamp}
        )

    @staticmethod
    def from_event(event: Event) -> "Detection":
        assert event.data is not None
        return Detection(
            name=event.data.get("name"), timestamp=event.data.get("timestamp")
        )


@dataclass
class NotDetected(Eventable):
    """Audio stream ended before wake word was detected."""

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _NOT_DETECTED_TYPE

    def event(self) -> Event:
        return Event(type=_NOT_DETECTED_TYPE)

    @staticmethod
    def from_event(event: Event) -> "NotDetected":
        return NotDetected()
