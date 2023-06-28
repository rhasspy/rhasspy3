"""Intent recognition and handling."""
import logging
from typing import Optional, Union

from wyoming.handle import Handled, NotHandled

from .asr import Transcript
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import async_read_event, async_write_event
from .intent import Intent, NotRecognized
from .program import create_process

DOMAIN = "handle"

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "Handled",
    "NotHandled",
    "handle",
    "DOMAIN",
]


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
