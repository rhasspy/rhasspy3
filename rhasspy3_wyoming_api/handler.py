"""Event handler for clients of the server."""
import logging
import asyncio

from rhasspy3.core import Rhasspy
from rhasspy3.config import PipelineConfig
from rhasspy3.event import Event, async_read_event, async_write_event
from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.asr import Transcript, DOMAIN as ASR_DOMAIN
from rhasspy3.tts import Synthesize, DOMAIN as TTS_DOMAIN
from rhasspy3.vad import DOMAIN as VAD_DOMAIN
from rhasspy3.intent import Intent, Recognize, NotRecognized, DOMAIN as INTENT_DOMAIN
from rhasspy3.handle import Handled, NotHandled, DOMAIN as HANDLE_DOMAIN
from rhasspy3.wake import Detection, NotDetected, DOMAIN as WAKE_DOMAIN
from rhasspy3.snd import Played, DOMAIN as SND_DOMAIN
from rhasspy3.mic import DOMAIN as MIC_DOMAIN

from wyoming.asr import Transcribe
from wyoming.wake import Detect
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler

from .process import PipelineProcessManager

_LOGGER = logging.getLogger(__name__)
PROC_READ_TIMEOUT = 27


class PipelineEventHandler(AsyncEventHandler):
    def __init__(
        self,
        wyoming_info: Info,
        process_manager: PipelineProcessManager,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.wyoming_info_event = wyoming_info.event()
        self.process_manager = process_manager
        self.domain = None
        self.lock = None
        self.process_listener = None

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        # Recognize the domain by the first event
        # TODO: better recognition of vad, asr, wake, and snd domains
        if self.domain is None:
            if Synthesize.is_type(event.type):
                self.domain = TTS_DOMAIN
            elif Transcribe.is_type(event.type):
                self.domain = ASR_DOMAIN
            elif Detect.is_type(event.type):
                self.domain = WAKE_DOMAIN
            elif AudioChunk.is_type(event.type):
                self.domain = ASR_DOMAIN
            elif AudioStart.is_type(event.type):
                self.domain = VAD_DOMAIN
            elif Recognize.is_type(event.type):
                self.domain = INTENT_DOMAIN
            elif Transcript.is_type(event.type):
                self.domain = HANDLE_DOMAIN
            elif Intent.is_type(event.type):
                self.domain = HANDLE_DOMAIN
            elif NotRecognized.is_type(event.type):
                self.domain = HANDLE_DOMAIN
            else:
                raise RuntimeError("Unable to get domain for event: %s", event.type)
            _LOGGER.debug("Domain detected: %s", self.domain)

        if hasattr(self, f"handle_event_{self.domain}"):
            return await getattr(self, f"handle_event_{self.domain}")(event)
        else:
            raise RuntimeError("No handler for domain: %s", self.domain)

    async def disconnect(self) -> None:
        await super().disconnect()

        if self.domain is not None:
            await self.process_manager.terminate_process(self.domain)

        if self.lock is not None:
            try:
                self.lock.release()
            except RuntimeError:
                pass
            self.lock = None

        if self.process_listener is not None:
            self.process_listener.cancel()
            self.process_listener = None

    async def enable_stdio_forward(stop_eventables=[]):
        assert self.domain is not None

        proc = await self.process_manager.get_process(self.domain)

        assert proc.stdout is not None

        async def process_listener(proc, stop_eventables):
            while proc.returncode is None:
                try:
                    async with asyncio.timeout(PROC_READ_TIMEOUT):
                        proc_event = await async_read_event(proc.stdout)
                except TimeoutError:
                    _LOGGER.warning("Timeout reading from the process")
                    break

                if proc_event is None:
                    continue

                await self.write_event(proc_event)

                if any([cls.is_type(proc_event.type) for cls in stop_eventables]):
                    break

        if self.process_listener is None:
            self.process_listener = asyncio.get_running_loop().create_task(
                process_listener(proc)
            )

    async def handle_event_tts(self, event: Event) -> bool:
        assert self.domain == TTS_DOMAIN

        if not Synthesize.is_type(event.type):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        async with self.process_manager.processes_lock[self.domain]:
            proc = await self.process_manager.get_process(self.domain)

            assert proc.stdin is not None
            assert proc.stdout is not None

            await async_write_event(event, proc.stdin)

            while proc.returncode is None:
                try:
                    async with asyncio.timeout(PROC_READ_TIMEOUT):
                        proc_event = await async_read_event(proc.stdout)
                except TimeoutError:
                    _LOGGER.warning("Timeout reading from the process")
                    break

                if proc_event is None:
                    continue

                await self.write_event(proc_event)

                if AudioStop.is_type(proc_event.type):
                    break
        return False

    async def handle_event_intent(self, event: Event) -> bool:
        assert self.domain == INTENT_DOMAIN

        if not Recognize.is_type(event.type):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        async with self.process_manager.processes_lock[self.domain]:
            proc = await self.process_manager.get_process(self.domain)

            assert proc.stdin is not None
            assert proc.stdout is not None

            await async_write_event(event, proc.stdin)

            while proc.returncode is None:
                try:
                    async with asyncio.timeout(PROC_READ_TIMEOUT):
                        proc_event = await async_read_event(proc.stdout)
                except TimeoutError:
                    _LOGGER.warning("Timeout reading from the process")
                    break

                if proc_event is None:
                    continue

                await self.write_event(proc_event)

                if Intent.is_type(proc_event.type) or NotRecognized.is_type(
                    proc_event.type
                ):
                    break
        return False

    async def handle_event_handle(self, event: Event) -> bool:
        assert self.domain == HANDLE_DOMAIN

        if not Transcript.is_type(event.type):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        async with self.process_manager.processes_lock[self.domain]:
            proc = await self.process_manager.get_process(self.domain)

            assert proc.stdin is not None
            assert proc.stdout is not None

            await async_write_event(event, proc.stdin)

            while proc.returncode is None:
                try:
                    async with asyncio.timeout(PROC_READ_TIMEOUT):
                        proc_event = await async_read_event(proc.stdout)
                except TimeoutError:
                    _LOGGER.warning("Timeout reading from the process")
                    break

                if proc_event is None:
                    continue

                await self.write_event(proc_event)

                if Handled.is_type(proc_event.type) or NotHandled.is_type(
                    proc_event.type
                ):
                    break
        return False

    async def handle_event_asr(self, event: Event) -> bool:
        assert self.domain == ASR_DOMAIN

        if (
            not AudioStart.is_type(event.type)
            and not AudioChunk.is_type(event.type)
            and not AudioStop.is_type(event.type)
            and not Transcribe.is_type(event.type)
        ):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        if Transcribe.is_type(event.type):
            # Skip event as not supported by this version of Rhasspy
            return True

        if self.lock is None:
            self.lock = self.process_manager.processes_lock[self.domain]
            await self.lock.acquire()

        proc = await self.process_manager.get_process(self.domain)

        assert proc.stdin is not None
        assert proc.stdout is not None

        await async_write_event(event, proc.stdin)

        if not AudioStop.is_type(event.type):
            return True

        while proc.returncode is None:
            try:
                async with asyncio.timeout(PROC_READ_TIMEOUT):
                    proc_event = await async_read_event(proc.stdout)
            except TimeoutError:
                _LOGGER.warning("Timeout reading from the process")
                break

            if proc_event is None:
                continue

            await self.write_event(proc_event)

            if Transcript.is_type(proc_event.type):
                break

        return False

    async def handle_event_wake(self, event: Event) -> bool:
        assert self.domain == WAKE_DOMAIN

        if (
            not AudioStart.is_type(event.type)
            and not AudioChunk.is_type(event.type)
            and not AudioStop.is_type(event.type)
            and not Detect.is_type(event.type)
        ):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        if Detect.is_type(event.type):
            # Skip event as not supported by this version of Rhasspy
            return True

        if self.lock is None:
            self.lock = self.process_manager.processes_lock[self.domain]
            await self.lock.acquire()

        proc = await self.process_manager.get_process(self.domain)
        assert proc.stdin is not None

        if proc.returncode is not None:
            return False

        await async_write_event(event, proc.stdin)

        if self.process_listener is None:
            await self.enable_stdio_forward([Detection, NotDetected])

        return not self.process_listener.done()

    async def handle_event_vad(self, event: Event) -> bool:
        assert self.domain == VAD_DOMAIN

        if (
            not AudioStart.is_type(event.type)
            and not AudioChunk.is_type(event.type)
            and not AudioStop.is_type(event.type)
        ):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        if self.lock is None:
            self.lock = self.process_manager.processes_lock[self.domain]
            await self.lock.acquire()

        proc = await self.process_manager.get_process(self.domain)
        assert proc.stdin is not None

        if proc.returncode is not None:
            return False

        await async_write_event(event, proc.stdin)

        if self.process_listener is None:
            await self.enable_stdio_forward()

        return not self.process_listener.done()

    async def handle_event_snd(self, event: Event) -> bool:
        assert self.domain == SND_DOMAIN

        if (
            not AudioStart.is_type(event.type)
            and not AudioChunk.is_type(event.type)
            and not AudioStop.is_type(event.type)
        ):
            _LOGGER.warning("Unexpected event: %s", event)
            return True

        if self.lock is None:
            self.lock = self.process_manager.processes_lock[self.domain]
            await self.lock.acquire()

        proc = await self.process_manager.get_process(self.domain)
        assert proc.stdin is not None

        if proc.returncode is not None:
            return False

        await async_write_event(event, proc.stdin)

        if self.process_listener is None:
            await self.enable_stdio_forward([Played])

        return not self.process_listener.done()

    async def handle_event_mic(self, event: Event) -> bool:
        assert self.domain == MIC_DOMAIN

        if self.lock is None:
            self.lock = self.process_manager.processes_lock[self.domain]
            await self.lock.acquire()

        proc = await self.process_manager.get_process(self.domain)
        assert proc.stdin is not None

        if proc.returncode is not None:
            return False

        await async_write_event(event, proc.stdin)

        if self.process_listener is None:
            await self.enable_stdio_forward()

        return not self.process_listener.done()
