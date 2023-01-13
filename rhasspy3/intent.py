"""Intent recognition and handling."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, List

from .event import Event, Eventable

DOMAIN = "intent"
_INTENT_TYPE = "intent"
_NOT_RECOGNIZED_TYPE = "not-recognized"


@dataclass
class Entity:
    name: str
    value: Optional[Any] = None


@dataclass
class Intent(Eventable):
    name: str
    entities: Optional[List[Entity]] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _INTENT_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {"name": self.name}
        if self.entities:
            data["entities"] = [asdict(entity) for entity in self.entities]

        return Event(type=_INTENT_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "Intent":
        assert event.data is not None
        return Intent(name=event.data["name"], entities=event.data.get("entities"))


@dataclass
class NotRecognized(Eventable):
    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _NOT_RECOGNIZED_TYPE

    def event(self) -> Event:
        return Event(type=_NOT_RECOGNIZED_TYPE)

    @staticmethod
    def from_event(event: Event) -> "NotRecognized":
        return NotRecognized()
