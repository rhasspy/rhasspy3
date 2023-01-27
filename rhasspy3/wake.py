"""Wake word detection"""
import asyncio
from dataclasses import dataclass
from typing import MutableSequence, Optional, Union

from .audio import AudioChunk
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
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
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    mic_in: asyncio.StreamReader,
    chunk_buffer: Optional[MutableSequence[Event]] = None,
) -> Optional[Detection]:
    detection: Optional[Detection] = None
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
                    if chunk_buffer is not None:
                        chunk_buffer.append(mic_event)

                if detection is None:
                    # Next chunk
                    mic_task = asyncio.create_task(async_read_event(mic_in))
                    pending.add(mic_task)

            if detection is not None:
                # Ensure last mic task is finished
                break

            if wake_task in done:
                wake_event = wake_task.result()
                if wake_event is None:
                    break

                if Detection.is_type(wake_event.type):
                    detection = Detection.from_event(wake_event)
                else:
                    # Next wake event
                    wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
                    pending.add(wake_task)
    finally:
        wake_proc.terminate()
        asyncio.create_task(wake_proc.wait())

    return detection
