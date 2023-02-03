"""Audio output to speakers."""
import asyncio
import wave
from dataclasses import dataclass
from typing import IO, Optional, Union

from .audio import AudioStop, wav_to_chunks
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "snd"
_PLAYED_TYPE = "played"


@dataclass
class Played(Eventable):
    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _PLAYED_TYPE

    def event(self) -> Event:
        return Event(type=_PLAYED_TYPE)

    @staticmethod
    def from_event(event: Event) -> "Played":
        return Played()


async def play(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    wav_in: IO[bytes],
    samples_per_chunk: int,
    sleep: bool,
):
    wav_file: wave.Wave_read = wave.open(wav_in, "rb")
    with wav_file:
        async with (await create_process(rhasspy, DOMAIN, program)) as snd_proc:
            assert snd_proc.stdin is not None
            assert snd_proc.stdout is not None

            timestamp: Optional[int] = None
            for chunk in wav_to_chunks(wav_file, samples_per_chunk=samples_per_chunk):
                await async_write_event(chunk.event(), snd_proc.stdin)
                timestamp = chunk.timestamp

            if sleep:
                wav_seconds = wav_file.getnframes() / wav_file.getframerate()
                await asyncio.sleep(wav_seconds)

            await async_write_event(
                AudioStop(timestamp=timestamp).event(), snd_proc.stdin
            )

            # Wait for confimation
            while True:
                event = await async_read_event(snd_proc.stdout)
                if event is None:
                    break

                if Played.is_type(event.type):
                    break
