"""Speech to text."""
import wave
from dataclasses import dataclass
from typing import IO, Optional

from .audio import AudioStart, AudioStop, wav_to_chunks
from .core import Rhasspy
from .event import async_read_event, async_write_event, Event, Eventable
from .program import create_process

DOMAIN = "asr"
_TRANSCRIPT_TYPE = "transcript"


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
    rhasspy: Rhasspy, program: str, wav_in: IO[bytes], samples_per_chunk: int
) -> Optional[Transcript]:
    wav_file: wave.Wave_read = wave.open(wav_in, "rb")
    with wav_file:
        rate = wav_file.getframerate()
        width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()

        asr_proc = await create_process(rhasspy, DOMAIN, program)
        try:
            assert asr_proc.stdin is not None
            assert asr_proc.stdout is not None

            timestamp = 0
            await async_write_event(
                AudioStart(rate, width, channels, timestamp=timestamp).event(),
                asr_proc.stdin,
            )

            for chunk in wav_to_chunks(wav_file, samples_per_chunk=samples_per_chunk):
                await async_write_event(chunk.event(), asr_proc.stdin)
                if chunk.timestamp is not None:
                    timestamp = chunk.timestamp
                else:
                    timestamp += chunk.milliseconds

            await async_write_event(AudioStop(timestamp=timestamp).event(), asr_proc.stdin)

            while True:
                event = await async_read_event(asr_proc.stdout)
                if event is None:
                    break

                if Transcript.is_type(event.type):
                    return Transcript.from_event(event)
        finally:
            asr_proc.terminate()
            await asr_proc.wait()

    return None
