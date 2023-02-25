"""Speech to text."""
import asyncio
import logging
import wave
from dataclasses import dataclass
from typing import IO, AsyncIterable, Optional, Union

from .audio import AudioChunk, AudioStart, AudioStop, wav_to_chunks
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, Eventable, async_read_event, async_write_event
from .program import create_process
from .vad import DOMAIN as VAD_DOMAIN, VoiceStopped, VoiceStarted

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


async def transcribe_stream(
    rhasspy: Rhasspy,
    asr_program: Union[str, PipelineProgramConfig],
    vad_program: Union[str, PipelineProgramConfig],
    audio_stream: AsyncIterable[bytes],
    rate: int,
    width: int,
    channels: int,
) -> Optional[Transcript]:
    transcript: Optional[Transcript] = None
    async with (await create_process(rhasspy, DOMAIN, asr_program)) as asr_proc, (
        await create_process(rhasspy, VAD_DOMAIN, vad_program)
    ) as vad_proc:
        assert asr_proc.stdin is not None
        assert asr_proc.stdout is not None
        assert vad_proc.stdin is not None
        assert vad_proc.stdout is not None

        timestamp = 0
        audio_start_event = AudioStart(
            rate, width, channels, timestamp=timestamp
        ).event()
        await asyncio.gather(
            async_write_event(
                audio_start_event,
                asr_proc.stdin,
            ),
            async_write_event(
                audio_start_event,
                vad_proc.stdin,
            ),
        )

        async def next_chunk():
            """Get the next chunk from audio stream."""
            async for chunk_bytes in audio_stream:
                return chunk_bytes

        is_first_chunk = True
        audio_task = asyncio.create_task(next_chunk())
        vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
        pending = {audio_task, vad_task}

        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            if vad_task in done:
                vad_event = vad_task.result()
                if vad_event is None:
                    break

                if VoiceStarted.is_type(vad_event.type):
                    _LOGGER.debug("transcribe: voice started")
                elif VoiceStopped.is_type(vad_event.type):
                    _LOGGER.debug("transcribe: voice stopped")
                    break

                vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
                pending.add(vad_task)

            if audio_task in done:
                chunk_bytes = audio_task.result()
                if not chunk_bytes:
                    # End of audio stream
                    break

                if is_first_chunk:
                    _LOGGER.debug("transcribe: processing audio")
                    is_first_chunk = False

                chunk = AudioChunk(rate, width, channels, chunk_bytes)
                chunk_event = chunk.event()
                await asyncio.gather(
                    async_write_event(chunk_event, asr_proc.stdin),
                    async_write_event(chunk_event, vad_proc.stdin),
                )
                timestamp += chunk.milliseconds

                audio_task = asyncio.create_task(next_chunk())
                pending.add(audio_task)

        await async_write_event(AudioStop(timestamp=timestamp).event(), asr_proc.stdin)
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
