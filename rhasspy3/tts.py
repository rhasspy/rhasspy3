"""Text to speech."""
import asyncio
import wave
from dataclasses import dataclass
from typing import IO, Union

from .audio import AudioChunk, AudioStart, AudioStop
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "tts"
_SYNTHESIZE_TYPE = "synthesize"


@dataclass
class Synthesize(Eventable):
    text: str

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _SYNTHESIZE_TYPE

    def event(self) -> Event:
        return Event(type=_SYNTHESIZE_TYPE, data={"text": self.text})

    @staticmethod
    def from_event(event: Event) -> "Synthesize":
        assert event.data is not None
        return Synthesize(text=event.data["text"])


async def synthesize(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    text: str,
    wav_out: IO[bytes],
):
    tts_proc = await create_process(rhasspy, DOMAIN, program)
    try:
        assert tts_proc.stdin is not None
        assert tts_proc.stdout is not None

        await async_write_event(Synthesize(text=text).event(), tts_proc.stdin)

        wav_file: wave.Wave_write = wave.open(wav_out, "wb")
        with wav_file:
            audio_started = False
            while True:
                event = await async_read_event(tts_proc.stdout)
                if event is None:
                    break

                if AudioStart.is_type(event.type):
                    start = AudioStart.from_event(event)
                    wav_file.setframerate(start.rate)
                    wav_file.setsampwidth(start.width)
                    wav_file.setnchannels(start.channels)
                    audio_started = True
                elif AudioChunk.is_type(event.type):
                    if audio_started:
                        chunk = AudioChunk.from_event(event)
                        wav_file.writeframes(chunk.audio)
                elif AudioStop.is_type(event.type):
                    break
    finally:
        tts_proc.terminate()
        asyncio.create_task(tts_proc.wait())
