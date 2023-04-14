"""Intent recognition and handling."""
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from .asr import Transcript
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .intent import Intent, NotRecognized
from .program import create_process

DOMAIN = "handle"
_HANDLED_TYPE = "handled"
_NOT_HANDLED_TYPE = "not-handled"

_LOGGER = logging.getLogger(__name__)


@dataclass
class Handled(Eventable):
    text: Optional[str] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _HANDLED_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {}
        if self.text is not None:
            data["text"] = self.text

        return Event(type=_HANDLED_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "Handled":
        assert event.data is not None
        return Handled(text=event.data.get("text"))


@dataclass
class NotHandled(Eventable):
    text: Optional[str] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _NOT_HANDLED_TYPE

    def event(self) -> Event:
        data: Dict[str, Any] = {}
        if self.text is not None:
            data["text"] = self.text

        return Event(type=_NOT_HANDLED_TYPE, data=data)

    @staticmethod
    def from_event(event: Event) -> "NotHandled":
        assert event.data is not None
        return NotHandled(text=event.data.get("text"))


async def handle(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    handle_input: Union[Intent, NotRecognized, Transcript],
) -> Optional[Union[Handled, NotHandled]]:
    handle_result: Optional[Union[Handled, NotHandled]] = None
    async with (await create_process(rhasspy, DOMAIN, program)) as handle_proc:
        assert handle_proc.stdin is not None
        assert handle_proc.stdout is not None

        _LOGGER.debug("handle: input=%s", handle_input)
        await async_write_event(handle_input.event(), handle_proc.stdin)
        while True:
            event = await async_read_event(handle_proc.stdout)
            if event is None:
                break

            if Handled.is_type(event.type):
                handle_result = Handled.from_event(event)
                break

            if NotHandled.is_type(event.type):
                handle_result = NotHandled.from_event(event)
                break

    _LOGGER.debug("handle: %s", handle_result)

    return handle_result
