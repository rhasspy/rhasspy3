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
    """User has started speaking."""

    timestamp: Optional[int] = None
    """Milliseconds"""

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
    """User has stopped speaking."""

    timestamp: Optional[int] = None
    """Milliseconds"""

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


@dataclass
class Segmenter:
    """Segments an audio stream by speech."""

    speech_seconds: float
    """Seconds of speech before voice command has started."""

    silence_seconds: float
    """Seconds of silence after voice command has ended."""

    timeout_seconds: float
    """Maximum number of seconds before stopping with timeout=True."""

    reset_seconds: float
    """Seconds before reset start/stop time counters."""

    started: bool = False
    """True if user has started speaking"""

    start_timestamp: Optional[int] = None
    """Timestamp when user started speaking."""

    stopped: bool = False
    """True if user has stopped speaking"""

    stop_timestamp: Optional[int] = None
    """Timestamp when user stopped speaking."""

    timeout: bool = False
    """True if stopping was due to timeout."""

    _in_command: bool = False
    """True if inside voice command."""

    _speech_seconds_left: float = 0.0
    """Seconds left before considering voice command as started."""

    _silence_seconds_left: float = 0.0
    """Seconds left before considering voice command as stopped."""

    _timeout_seconds_left: float = 0.0
    """Seconds left before considering voice command timed out."""

    _reset_seconds_left: float = 0.0
    """Seconds left before resetting start/stop time counters."""

    def __post_init__(self):
        self.reset()

    def reset(self):
        """Resets all counters and state."""
        self._speech_seconds_left = self.speech_seconds
        self._silence_seconds_left = self.silence_seconds
        self._timeout_seconds_left = self.timeout_seconds
        self._reset_seconds_left = self.reset_seconds
        self._in_command = False
        self.start_timestamp = None
        self.stop_timestamp = None

    def process(
        self, chunk: bytes, chunk_seconds: float, is_speech: bool, timestamp: int
    ):
        """Process a single chunk of audio."""
        self._timeout_seconds_left -= chunk_seconds
        if self._timeout_seconds_left <= 0:
            self.stop_timestamp = timestamp
            self.timeout = True
            self.stopped = True
            return

        if not self._in_command:
            if is_speech:
                self._reset_seconds_left = self.reset_seconds

                if self.start_timestamp is None:
                    self.start_timestamp = timestamp

                self._speech_seconds_left -= chunk_seconds
                if self._speech_seconds_left <= 0:
                    # Inside voice command
                    self._in_command = True
                    self.started = True
            else:
                # Reset if enough silence
                self._reset_seconds_left -= chunk_seconds
                if self._reset_seconds_left <= 0:
                    self._speech_seconds_left = self.speech_seconds
                    self.start_timestamp = None
        else:
            if not is_speech:
                self._reset_seconds_left = self.reset_seconds
                self._silence_seconds_left -= chunk_seconds
                if self._silence_seconds_left <= 0:
                    self.stop_timestamp = timestamp
                    self.stopped = True
            else:
                # Reset if enough speech
                self._reset_seconds_left -= chunk_seconds
                if self._reset_seconds_left <= 0:
                    self._silence_seconds_left = self.silence_seconds


async def segment(
    rhasspy: Rhasspy,
    program: Union[str, PipelineProgramConfig],
    mic_in: asyncio.StreamReader,
    asr_out: asyncio.StreamWriter,
    chunk_buffer: Optional[Iterable[Event]] = None,
):
    """Segments an audio input stream, passing audio chunks to asr."""
    async with (await create_process(rhasspy, DOMAIN, program)) as vad_proc:
        assert vad_proc.stdin is not None
        assert vad_proc.stdout is not None

        if chunk_buffer:
            # Buffered chunks from wake word detection
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
        is_first_chunk = True

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
                    if is_first_chunk:
                        is_first_chunk = False
                        _LOGGER.debug("segment: processing audio")

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
                        _LOGGER.debug("segment: speaking started")
                elif VoiceStopped.is_type(vad_event.type):
                    # End of voice command
                    _LOGGER.debug("segment: speaking ended")
                    await async_write_event(
                        AudioStop(timestamp=timestamp).event(), asr_out
                    )
                    break

                # Next VAD event
                vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
                pending.add(vad_task)
