"""Text to speech."""
import wave
from dataclasses import dataclass
from typing import IO, AsyncIterable, Union

from .audio import AudioChunk, AudioStart, AudioStop
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "tts"
_SYNTHESIZE_TYPE = "synthesize"


@dataclass
class Synthesize(Eventable):
    """Request to synthesize audio from text."""

    text: str
    """Text to synthesize."""

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
    """Synthesize audio from text to WAV output."""
    async with (await create_process(rhasspy, DOMAIN, program)) as tts_proc:
        assert tts_proc.stdin is not None
        assert tts_proc.stdout is not None

        await async_write_event(Synthesize(text=text).event(), tts_proc.stdin)

        wav_file: wave.Wave_write = wave.open(wav_out, "wb")
        wav_params_set = False
        with wav_file:
            while True:
                event = await async_read_event(tts_proc.stdout)
                if event is None:
                    break

                if AudioStart.is_type(event.type):
                    if not wav_params_set:
                        start = AudioStart.from_event(event)
                        wav_file.setframerate(start.rate)
                        wav_file.setsampwidth(start.width)
                        wav_file.setnchannels(start.channels)
                        wav_params_set = True
                elif AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)

                    if not wav_params_set:
                        wav_file.setframerate(chunk.rate)
                        wav_file.setsampwidth(chunk.width)
                        wav_file.setnchannels(chunk.channels)
                        wav_params_set = True

                    wav_file.writeframes(chunk.audio)
                elif AudioStop.is_type(event.type):
                    break


async def synthesize_stream(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    text: str,
) -> AsyncIterable[AudioChunk]:
    """Synthesize audio from text to a raw stream."""
    async with (await create_process(rhasspy, DOMAIN, program)) as tts_proc:
        assert tts_proc.stdin is not None
        assert tts_proc.stdout is not None

        await async_write_event(Synthesize(text=text).event(), tts_proc.stdin)

        while True:
            event = await async_read_event(tts_proc.stdout)
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                yield AudioChunk.from_event(event)
            elif AudioStop.is_type(event.type):
                break
