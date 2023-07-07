"""Wake word detection"""
import asyncio
import logging
import wave
from collections import deque
from typing import AsyncIterable, Deque, MutableSequence, Optional, Union

from wyoming.wake import Detection, NotDetected

from .audio import AudioChunk, AudioStart, AudioStop
from .config import PipelineProgramConfig
from .core import Rhasspy
from .event import Event, async_read_event, async_write_event
from .program import create_process

DOMAIN = "wake"

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "DOMAIN",
    "Detection",
    "NotDetected",
    "detect",
    "detect_stream",
]


async def detect(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    mic_in: asyncio.StreamReader,
    chunk_buffer: Optional[MutableSequence[Event]] = None,
    save_wav_writer: Optional[wave.Wave_write] = None,
    save_wav_chunks: int = 40,
) -> Optional[Detection]:
    """Try to detect wake word in an audio stream."""
    detection: Optional[Detection] = None
    saved_chunks: Deque[Event] = deque(maxlen=save_wav_chunks)
    async with (await create_process(rhasspy, DOMAIN, program)) as wake_proc:
        assert wake_proc.stdin is not None
        assert wake_proc.stdout is not None

        mic_task = asyncio.create_task(async_read_event(mic_in))
        wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
        pending = {mic_task, wake_task}
        is_first_chunk = True

        try:
            while True:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if mic_task in done:
                    mic_event = mic_task.result()
                    if mic_event is None:
                        break

                    if AudioChunk.is_type(mic_event.type):
                        if is_first_chunk:
                            is_first_chunk = False
                            _LOGGER.debug("detect: processing audio")

                        await async_write_event(mic_event, wake_proc.stdin)
                        if chunk_buffer is not None:
                            # Buffer chunks for asr
                            chunk_buffer.append(mic_event)

                        if save_wav_writer is not None:
                            saved_chunks.append(mic_event)

                    # Next chunk
                    mic_task = asyncio.create_task(async_read_event(mic_in))
                    pending.add(mic_task)

                if detection is not None:
                    await async_write_event(AudioStop().event(), wake_proc.stdin)

                    if save_wav_writer is not None:
                        save_wav_writer_set = False
                        for chunk_event in saved_chunks:
                            chunk = AudioChunk.from_event(chunk_event)
                            if not save_wav_writer_set:
                                # Configure WAV
                                save_wav_writer.setframerate(chunk.rate)
                                save_wav_writer.setsampwidth(chunk.width)
                                save_wav_writer.setnchannels(chunk.channels)
                                save_wav_writer_set = True

                            save_wav_writer.writeframes(chunk.audio)

                    break

                if wake_task in done:
                    wake_event = wake_task.result()
                    if wake_event is None:
                        break

                    if Detection.is_type(wake_event.type):
                        detection = Detection.from_event(wake_event)
                    else:
                        # Next wake event
                        wake_task = asyncio.create_task(
                            async_read_event(wake_proc.stdout)
                        )
                        pending.add(wake_task)
        finally:
            for task in pending:
                task.cancel()

    _LOGGER.debug("detect: %s", detection)

    return detection


async def detect_stream(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    audio_stream: AsyncIterable[bytes],
    rate: int,
    width: int,
    channels: int,
) -> Optional[Detection]:
    """Try to detect the wake word in a raw audio stream."""
    async with (await create_process(rhasspy, DOMAIN, program)) as wake_proc:
        assert wake_proc.stdin is not None
        assert wake_proc.stdout is not None

        timestamp = 0
        await async_write_event(
            AudioStart(rate, width, channels, timestamp=timestamp).event(),
            wake_proc.stdin,
        )

        async def next_chunk():
            """Get the next chunk from audio stream."""
            async for chunk_bytes in audio_stream:
                return chunk_bytes

        audio_task = asyncio.create_task(next_chunk())
        wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
        pending = {audio_task, wake_task}

        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            if audio_task in done:
                chunk_bytes = audio_task.result()
                if chunk_bytes:
                    chunk = AudioChunk(rate, width, channels, chunk_bytes)
                    await async_write_event(chunk.event(), wake_proc.stdin)
                    timestamp += chunk.milliseconds

                    audio_task = asyncio.create_task(next_chunk())
                    pending.add(audio_task)
                else:
                    wake_task.cancel()
                    await async_write_event(AudioStop().event(), wake_proc.stdin)
                    wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
                    pending = {wake_task}

            if wake_task in done:
                wake_event = wake_task.result()
                if wake_event is None:
                    break

                if Detection.is_type(wake_event.type):
                    detection = Detection.from_event(wake_event)
                    _LOGGER.debug("detect: %s", detection)
                    return detection

                if NotDetected.is_type(wake_event.type):
                    break

                wake_task = asyncio.create_task(async_read_event(wake_proc.stdout))
                pending.add(wake_task)

        _LOGGER.debug("Not detected")

    return None
