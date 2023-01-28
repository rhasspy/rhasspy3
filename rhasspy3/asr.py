"""Speech to text."""
import logging
import wave
from dataclasses import dataclass
from typing import IO, Optional, Union

from .audio import AudioStart, AudioStop, wav_to_chunks
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process

DOMAIN = "asr"
_TRANSCRIPT_TYPE = "transcript"

_LOGGER = logging.getLogger(__name__)


@dataclass
class Transcript(Eventable):
    text: str

    @staticmethod
    def is_type(event_type: str) -> bool:
        return event_type == _TRANSCRIPT_TYPE

    def event(self) -> Event:
        return Event(type=_TRANSCRIPT_TYPE, data={"text": self.text})

    @staticmethod
    def from_event(event: Event) -> "Transcript":
        assert event.data is not None
        return Transcript(text=event.data["text"])


async def transcribe(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    wav_in: IO[bytes],
    samples_per_chunk: int,
) -> Optional[Transcript]:
    transcript: Optional[Transcript] = None
    wav_file: wave.Wave_read = wave.open(wav_in, "rb")
    with wav_file:
        rate = wav_file.getframerate()
        width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()

        async with (await create_process(rhasspy, DOMAIN, program)) as asr_proc:
            assert asr_proc.stdin is not None
            assert asr_proc.stdout is not None

            timestamp = 0
            await async_write_event(
                AudioStart(rate, width, channels, timestamp=timestamp).event(),
                asr_proc.stdin,
            )

            is_first_chunk = True

            for chunk in wav_to_chunks(wav_file, samples_per_chunk=samples_per_chunk):
                if is_first_chunk:
                    is_first_chunk = False
                    _LOGGER.debug("transcribe: processing audio")

                await async_write_event(chunk.event(), asr_proc.stdin)
                if chunk.timestamp is not None:
                    timestamp = chunk.timestamp
                else:
                    timestamp += chunk.milliseconds

            await async_write_event(
                AudioStop(timestamp=timestamp).event(), asr_proc.stdin
            )

            _LOGGER.debug("transcribe: audio finished")

            while True:
                event = await async_read_event(asr_proc.stdout)
                if event is None:
                    break

                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event)
                    _LOGGER.debug("transcribe: %s", transcript)
                    break

    return transcript
