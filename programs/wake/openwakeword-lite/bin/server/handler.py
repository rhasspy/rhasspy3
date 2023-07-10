"""Event handler for clients of the server."""
import argparse
import asyncio
import logging
from typing import Optional
from uuid import uuid4

import numpy as np

from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.wake import Detection, NotDetected

from .const import ClientData, WakeWordData
from .state import State

_LOGGER = logging.getLogger(__name__)


class OpenWakeWordEventHandler(AsyncEventHandler):
    def __init__(
        self,
        wyoming_info: Info,
        cli_args: argparse.Namespace,
        state: State,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.wyoming_info_event = wyoming_info.event()
        self.client_id = str(uuid4())
        self.state = state
        self.data: Optional[ClientData] = None
        self.is_detected = False
        self.converter = AudioChunkConverter(rate=16000, width=2, channels=1)

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        if self.data is None:
            # Create buffers for this client
            self.data = ClientData(self)
            with self.state.clients_lock:
                self.state.clients[self.client_id] = self.data
                for ww_name in self.state.wake_words:
                    self.data.wake_words[ww_name] = WakeWordData()

        if AudioStart.is_type(event.type):
            # Reset
            self.is_detected = False
            with self.state.audio_lock:
                self.data.reset()
        elif AudioChunk.is_type(event.type):
            # Add to audio buffer and signal mels thread
            chunk = self.converter.convert(AudioChunk.from_event(event))
            chunk_array = np.frombuffer(chunk.audio, dtype=np.int16).astype(np.float32)
            with self.state.audio_lock:
                # Shift samples left
                self.data.audio[: -len(chunk_array)] = self.data.audio[
                    len(chunk_array) :
                ]

                # Add new samples to end
                self.data.audio[-len(chunk_array) :] = chunk_array
                self.data.new_audio_samples = min(
                    len(self.data.audio),
                    self.data.new_audio_samples + len(chunk_array),
                )

            # Signal mels thread that audio is ready to process
            self.state.audio_ready.release()
        elif AudioStop.is_type(event.type):
            # Inform client if not detections occurred
            if not self.is_detected:
                # No wake word detections
                await self.write_event(NotDetected().event())

            return False

        return True

    async def disconnect(self) -> None:
        if self.data is None:
            return

        with self.state.clients_lock:
            self.state.clients.pop(self.client_id, None)
