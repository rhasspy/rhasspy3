"""Audio input from a microphone."""
from typing import Union

from .audio import AudioStop
from .config import PipelineProgramConfig
from .core import Rhasspy
from .program import create_process
from .event import async_write_event

DOMAIN = "mic"

__all__ = [
    "DOMAIN",
    "record",
]


class RecordContextManager:
    """Wrapper for an async microphone process that terminates on exit."""

    def __init__(
        self,
        rhasspy: Rhasspy,
        program: Union[str, PipelineProgramConfig],
    ):
        self.rhasspy = rhasspy
        self.program = program
        self.proc_context = None

    async def __aenter__(self):
        self.proc_context = await create_process(self.rhasspy, DOMAIN, self.program)
        return await self.proc_context.__aenter__()

    async def __aexit__(self, exc_type, exc, tb):
        assert self.proc_context.proc.stdin is not None
        await async_write_event(AudioStop().event(), self.proc_context.proc.stdin)
        await self.proc_context.__aexit__(exc_type, exc, tb)


def record(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
):
    return RecordContextManager(rhasspy, program)
