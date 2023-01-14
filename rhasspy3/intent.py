"""Intent recognition and handling."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, List

from .event import Event, Eventable

DOMAIN = "intent"
_RECOGNIZE_TYPE = "recognize"
_INTENT_TYPE = "intent"
_NOT_RECOGNIZED_TYPE = "not-recognized"


@dataclass
class Entity:
    name: str
    value: Optional[Any] = None


@dataclass
class Recognize(Eventable):
    text: str

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _RECOGNIZE_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {"text": self.text}
        return Event(type=_RECOGNIZE_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "Recognize":
        assert event.data is not None
        return Recognize(text=event.data["text"])


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
        entities: Optional[List[Entity]] = None
        entity_dicts = event.data.get("entities")
        if entity_dicts:
            entities = [Entity(**entity_dict) for entity_dict in entity_dicts]

        return Intent(name=event.data["name"], entities=entities)


@dataclass
class NotRecognized(Eventable):
    text: Optional[str] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _NOT_RECOGNIZED_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {}
        if self.text is not None:
            data["text"] = self.text

        return Event(type=_NOT_RECOGNIZED_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "NotRecognized":
        assert event.data is not None
        return NotRecognized(text=event.data.get("text"))
