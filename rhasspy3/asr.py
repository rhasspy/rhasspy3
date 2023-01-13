"""Speech to text."""
from dataclasses import dataclass

from .event import Event, Eventable

DOMAIN = "asr"
_TRANSCRIPT_TYPE = "transcript"


@dataclass
class Transcript(Eventable):
    text: str

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _TRANSCRIPT_TYPE

    def event(self) -> Event:
        return Event(type=_TRANSCRIPT_TYPE, data={"text": self.text})

    @staticmethod
    def from_event(event: Event) -> "Transcript":
        assert event.data is not None
        return Transcript(text=event.data["text"])
