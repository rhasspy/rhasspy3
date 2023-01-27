"""Voice activity detection."""
import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Union

from .audio import AudioChunk, AudioStop
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "vad"
_STARTED_TYPE = "voice-started"
_STOPPED_TYPE = "voice-stopped"

_LOGGER = logging.getLogger(__name__)


@dataclass
class VoiceStarted(Eventable):
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _STARTED_TYPE

    def event(self) -> Event:
        return Event(
            type=_STARTED_TYPE,
            data={"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "VoiceStarted":
        return VoiceStarted(timestamp=event.data.get("timestamp"))


@dataclass
class VoiceStopped(Eventable):
    timestamp: Optional[int] = None

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _STOPPED_TYPE

    def event(self) -> Event:
        return Event(
            type=_STOPPED_TYPE,
            data={"timestamp": self.timestamp},
        )

    @staticmethod
    def from_event(event: Event) -> "VoiceStopped":
        return VoiceStopped(timestamp=event.data.get("timestamp"))


async def segment(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    mic_in: asyncio.StreamReader,
    asr_out: asyncio.StreamWriter,
    chunk_buffer: Optional[Iterable[Event]] = None,
):
    vad_proc = await create_process(rhasspy, DOMAIN, program)
    try:
        assert vad_proc.stdin is not None
        assert vad_proc.stdout is not None

        if chunk_buffer:
            for buffered_event in chunk_buffer:
                await asyncio.gather(
                    async_write_event(buffered_event, vad_proc.stdin),
                    async_write_event(buffered_event, asr_out),
                )

        mic_task = asyncio.create_task(async_read_event(mic_in))
        vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
        pending = {mic_task, vad_task}

        timestamp = 0
        in_command = False

        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            if mic_task in done:
                mic_event = mic_task.result()
                if mic_event is None:
                    break

                # Process chunk
                if AudioChunk.is_type(mic_event.type):
                    chunk = AudioChunk.from_event(mic_event)
                    timestamp = (
                        chunk.timestamp
                        if chunk.timestamp is not None
                        else time.monotonic_ns()
                    )

                    if in_command:
                        # Speech recognition and silence detection
                        await asyncio.gather(
                            async_write_event(mic_event, asr_out),
                            async_write_event(mic_event, vad_proc.stdin),
                        )
                    else:
                        # Voice detection
                        await asyncio.gather(
                            async_write_event(mic_event, asr_out),
                            async_write_event(mic_event, vad_proc.stdin),
                        )

                # Next chunk
                mic_task = asyncio.create_task(async_read_event(mic_in))
                pending.add(mic_task)

            if vad_task in done:
                vad_event = vad_task.result()
                if vad_event is None:
                    break

                if VoiceStarted.is_type(vad_event.type):
                    if not in_command:
                        # Start of voice command
                        in_command = True
                        _LOGGER.debug("segment: started")
                elif VoiceStopped.is_type(vad_event.type):
                    # End of voice command
                    _LOGGER.debug("segment: ended")
                    await async_write_event(
                        AudioStop(timestamp=timestamp).event(), asr_out
                    )
                    break

                # Next VAD event
                vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
                pending.add(vad_task)
    finally:
        vad_proc.terminate()
        asyncio.create_task(vad_proc.wait())
