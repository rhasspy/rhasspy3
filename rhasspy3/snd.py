"""Audio output to speakers."""
import asyncio
import wave
from typing import IO, Union

from .audio import wav_to_chunks
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import async_write_event
from .program import create_process

DOMAIN = "snd"


async def play(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    wav_in: IO[bytes],
    samples_per_chunk: int,
    sleep: bool,
):
    wav_file: wave.Wave_read = wave.open(wav_in, "rb")
    with wav_file:
        snd_proc = await create_process(rhasspy, DOMAIN, program)
        try:
            assert snd_proc.stdin is not None

            for chunk in wav_to_chunks(wav_file, samples_per_chunk=samples_per_chunk):
                await async_write_event(chunk.event(), snd_proc.stdin)

            if sleep:
                wav_seconds = wav_file.getnframes() / wav_file.getframerate()
                await asyncio.sleep(wav_seconds)
        finally:
            snd_proc.terminate()
            asyncio.create_task(snd_proc.wait())
