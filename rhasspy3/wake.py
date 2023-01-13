"""Wake word detection"""
from dataclasses import dataclass
from typing import Optional

from .event import Event, Eventable

DOMAIN = "wake"
_DETECTION_TYPE = "detection"


@dataclass
class Detection(Eventable):
    name: Optional[str] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _DETECTION_TYPE

    def event(self) -> Event:
        return Event(type=_DETECTION_TYPE, data={"name": self.name})

    @staticmethod
    def from_event(event: Event) -> "Detection":
        assert event.data is not None
        return Detection(name=event.data.get("name"))
