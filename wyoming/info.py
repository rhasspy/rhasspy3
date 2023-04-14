"""Information about available services/artifacts."""
from dataclasses import dataclass
from typing import Any, Dict, List

from .event import Event, Eventable
from .util.dataclasses_json import DataClassJsonMixin

DOMAIN = "info"
_DESCRIBE_TYPE = "describe"
_INFO_TYPE = "info"


@dataclass
class Describe(Eventable):
    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _DESCRIBE_TYPE

    def event(self) -> Event:
        return Event(type=_DESCRIBE_TYPE)

    @staticmethod
    def from_event(event: Event) -> "Describe":
        return Describe()


@dataclass
class Attribution(DataClassJsonMixin):
    name: str
    url: str


@dataclass
class Artifact(DataClassJsonMixin):
    name: str
    attribution: Attribution
    installed: bool


@dataclass
class AsrModel(Artifact):
    languages: List[str]


@dataclass
class AsrProgram(Artifact):
    models: List[AsrModel]


@dataclass
class TtsVoice(Artifact):
    name: str
    languages: List[str]


@dataclass
class TtsProgram(Artifact):
    voices: List[TtsVoice]


@dataclass
class Info(Eventable):
    asr: List[AsrProgram]
    tts: List[TtsProgram]

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _INFO_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {
            "asr": [p.to_dict() for p in self.asr],
            "tts": [p.to_dict() for p in self.tts],
        }

        return Event(type=_INFO_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "Info":
        assert event.data is not None
        return Info(
            asr=[AsrProgram.from_dict(d) for d in event.data.get("asr", [])],
            tts=[TtsProgram.from_dict(d) for d in event.data.get("tts", [])],
        )
