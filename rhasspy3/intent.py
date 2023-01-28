"""Intent recognition and handling."""
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Union

from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "intent"
_RECOGNIZE_TYPE = "recognize"
_INTENT_TYPE = "intent"
_NOT_RECOGNIZED_TYPE = "not-recognized"

_LOGGER = logging.getLogger(__name__)


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
    entities: List[Entity] = field(default_factory=list)

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
        entity_dicts = event.data.get("entities")
        if entity_dicts:
            entities: List[Entity] = [
                Entity(**entity_dict) for entity_dict in entity_dicts
            ]
        else:
            entities = []

        return Intent(name=event.data["name"], entities=entities)

    def to_rhasspy(self) -> Dict[str, Any]:
        return {
            "intent": {
                "name": self.name,
            },
            "entities": [
                {"entity": entity.name, "value": entity.value}
                for entity in self.entities
            ],
            "slots": {entity.name: entity.value for entity in self.entities},
        }


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


async def recognize(
    rhasspy: Rhasspy, program: Union[str, PipelineProgramConfig], text: str
) -> Optional[Union[Intent, NotRecognized]]:
    result: Optional[Union[Intent, NotRecognized]] = None
    async with (await create_process(rhasspy, DOMAIN, program)) as intent_proc:
        assert intent_proc.stdin is not None
        assert intent_proc.stdout is not None

        _LOGGER.debug("recognize: text='%s'", text)
        await async_write_event(Recognize(text=text).event(), intent_proc.stdin)
        while True:
            intent_event = await async_read_event(intent_proc.stdout)
            if intent_event is None:
                break

            if Intent.is_type(intent_event.type):
                result = Intent.from_event(intent_event)
                break

            if NotRecognized.is_type(intent_event.type):
                result = NotRecognized.from_event(intent_event)
                break

    _LOGGER.debug("recognize: %s", result)

    return result
