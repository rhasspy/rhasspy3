"""Information about available services/artifacts."""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .event import Event, Eventable

DOMAIN = "info"
_GET_INFO_TYPE = "get-info"
_INFO_TYPE = "info"


@dataclass
class GetInfo(Eventable):
    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _GET_INFO_TYPE

    def event(self) -> Event:
        return Event(type=_GET_INFO_TYPE)

    @staticmethod
    def from_event(event: Event) -> "GetInfo":
        return GetInfo()


@dataclass
class Artifact:
    description: str
    installed: bool
    source: str


@dataclass
class AsrArtifact(Artifact):
    languages: List[str]


@dataclass
class AsrInfo:
    description: str
    installed: bool
    artifacts: Optional[Dict[str, AsrArtifact]] = None


@dataclass
class TtsArtifact(Artifact):
    languages: List[str]


@dataclass
class TtsInfo:
    description: str
    installed: bool
    artifacts: Optional[Dict[str, TtsArtifact]] = None


@dataclass
class Info(Eventable):
    asr: Optional[Dict[str, AsrInfo]] = None
    tts: Optional[Dict[str, TtsInfo]] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _INFO_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {}
        if self.asr is not None:
            data["asr"] = self.asr
        if self.tts is not None:
            data["tts"] = self.tts

        return Event(type=_INFO_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "Info":
        assert event.data is not None
        return Info(
            asr=event.data.get("asr"),
            tts=event.data.get("tts"),
        )
