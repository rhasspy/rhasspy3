"""Intent recognition and handling."""
import logging
from typing import Optional, Union

from wyoming.intent import Entity, Intent, NotRecognized, Recognize

from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import async_read_event, async_write_event
from .program import create_process

DOMAIN = "intent"

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "DOMAIN",
    "Entity",
    "Intent",
    "Recognize",
    "NotRecognized",
    "recognize",
]


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
