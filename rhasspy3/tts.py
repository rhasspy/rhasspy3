"""Text to speech."""
from dataclasses import dataclass

from .event import Event, Eventable

DOMAIN = "tts"
_SYNTHESIZE_TYPE = "synthesize"


@dataclass
class Synthesize(Eventable):
    text: str

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _SYNTHESIZE_TYPE

    def event(self) -> Event:
        return Event(type=_SYNTHESIZE_TYPE, data={"text": self.text})

    @staticmethod
    def from_event(event: Event) -> "Synthesize":
        assert event.data is not None
        return Synthesize(text=event.data["text"])
