"""Audio output to speakers."""
import wave
from typing import IO

from .audio import wav_to_chunks
from .core import Rhasspy
from .event import async_write_event
from .program import create_process

DOMAIN = "snd"


async def play(
    rhasspy: Rhasspy, program: str, wav_in: IO[bytes], samples_per_chunk: int
):
    wav_file: wave.Wave_read = wave.open(wav_in, "rb")
    with wav_file:
        snd_proc = await create_process(rhasspy, DOMAIN, program)
        assert snd_proc.stdin is not None

        for chunk in wav_to_chunks(wav_file, samples_per_chunk=samples_per_chunk):
            await async_write_event(chunk.event(), snd_proc.stdin)
