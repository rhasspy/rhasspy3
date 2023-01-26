"""Wake word detection"""
import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from .audio import AudioChunk
from .core import Rhasspy
from .event import async_read_event, async_write_event, Event, Eventable
from .program import create_process

DOMAIN = "wake"
_DETECTION_TYPE = "detection"


@dataclass
class Detection(Eventable):
    name: Optional[str] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _DETECTION_TYPE

    def event(self) -> Event:
        return Event(type=_DETECTION_TYPE, data={"name": self.name})

    @staticmethod
    def from_event(event: Event) -> "Detection":
        assert event.data is not None
        return Detection(name=event.data.get("name"))


async def detect(
    rhasspy: Rhasspy, program: str, mic_in: asyncio.StreamReader
) -> Optional[Detection]:
    wake_proc = await create_process(rhasspy, DOMAIN, program)
    try:
        assert wake_proc.stdin is not None
        assert wake_proc.stdout is not None

        mic_task = asyncio.create_task(async_read_event(mic_in))
        wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
        pending = {mic_task, wake_task}

        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            if mic_task in done:
                mic_event = mic_task.result()
                if mic_event is None:
                    break

                if AudioChunk.is_type(mic_event.type):
                    await async_write_event(mic_event, wake_proc.stdin)

                # Next chunk
                mic_task = asyncio.create_task(async_read_event(mic_in))
                pending.add(mic_task)

            if wake_task in done:
                wake_event = wake_task.result()
                if wake_event is None:
                    break

                if Detection.is_type(wake_event.type):
                    return Detection.from_event(wake_event)

                # Next wake event
                wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
                pending.add(wake_task)
    finally:
        wake_proc.terminate()
        await wake_proc.wait()

    return None
