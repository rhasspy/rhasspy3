"""Event handler for clients of the server."""
import asyncio
import argparse
import logging
import time
import wave
from pathlib import Path
from threading import Thread
from typing import Final, List, Optional

import numpy as np

from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.wake import Detect, NotDetected

from .const import ClientData, WakeWordData
from .state import State, WakeWordState
from .openwakeword import ww_proc

_LOGGER = logging.getLogger(__name__)


class OpenWakeWordEventHandler(AsyncEventHandler):
    """Event handler for openWakeWord clients."""

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
        self.client_id = str(time.monotonic_ns())
        self.state = state
        self.data: Optional[ClientData] = None
        self.converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self.audio_buffer = bytes()

        # Only used when output_dir is set
        self.audio_writer: Optional[wave.Wave_write] = None

        _LOGGER.debug("Client connected: %s", self.client_id)

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info to client: %s", self.client_id)
            return True

        if self.data is None:
            # Create buffers for this client
            self.data = ClientData(self)
            with self.state.clients_lock:
                self.state.clients[self.client_id] = self.data
                for ww_name in self.state.wake_words:
                    self.data.wake_words[ww_name] = WakeWordData(
                        threshold=self.cli_args.threshold,
                        trigger_level=self.cli_args.trigger_level,
                    )

        if Detect.is_type(event.type):
            detect = Detect.from_event(event)
            if detect.names:
                _ensure_loaded(self.state, detect.names, self.cli_args)
        elif AudioStart.is_type(event.type):
            # Reset
            for ww_data in self.data.wake_words.values():
                ww_data.is_detected = False

            with self.state.audio_lock:
                self.data.reset()

            _LOGGER.debug("Receiving audio from client: %s", self.client_id)

            if self.cli_args.output_dir is not None:
                audio_start = AudioStart.from_event(event)
                audio_path = Path(self.cli_args.output_dir) / f"{self.client_id}.wav"
                self.audio_writer = wave.open(str(audio_path), "wb")
                self.audio_writer.setframerate(audio_start.rate)
                self.audio_writer.setsampwidth(audio_start.width)
                self.audio_writer.setnchannels(audio_start.channels)
                _LOGGER.debug("Saving audio to %s", audio_path)

        elif AudioChunk.is_type(event.type):
            # Add to audio buffer and signal mels thread
            chunk = self.converter.convert(AudioChunk.from_event(event))

            if self.audio_writer is not None:
                self.audio_writer.writeframes(chunk.audio)

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

                self.data.audio_timestamp = chunk.timestamp or time.monotonic_ns()

            # Signal mels thread that audio is ready to process
            self.state.audio_ready.release()
        elif AudioStop.is_type(event.type):
            # Inform client if not detections occurred
            if not any(
                ww_data.is_detected for ww_data in self.data.wake_words.values()
            ):
                # No wake word detections
                await self.write_event(NotDetected().event())

                _LOGGER.debug(
                    "Audio stopped without detection from client: %s", self.client_id
                )

            if self.audio_writer is not None:
                self.audio_writer.close()
                self.audio_writer = None

            return False
        else:
            _LOGGER.debug("Unexpected event: type=%s, data=%s", event.type, event.data)

        return True

    async def disconnect(self) -> None:
        _LOGGER.debug("Client disconnected: %s", self.client_id)

        if self.audio_writer is not None:
            self.audio_writer.close()
            self.audio_writer = None

        if self.data is None:
            return

        with self.state.clients_lock:
            self.state.clients.pop(self.client_id, None)


def _ensure_loaded(state: State, names: List[str], cli_args: argparse.Namespace):
    with state.ww_threads_lock, state.clients_lock:
        for model_key in names:
            ww_state = state.wake_words.get(model_key)
            if ww_state is not None:
                # Already loaded
                continue

            if model_key not in state.model_paths:
                _LOGGER.error("Unknown wake word model: %s", model_key)
                continue

            state.wake_words[model_key] = WakeWordState()
            state.ww_threads[model_key] = Thread(
                target=ww_proc,
                daemon=True,
                args=(
                    state,
                    model_key,
                    state.model_paths[model_key],
                    asyncio.get_running_loop(),
                ),
            )
            state.ww_threads[model_key].start()

            for client_data in state.clients.values():
                client_data.wake_words[model_key] = WakeWordData(
                    threshold=cli_args.threshold,
                    trigger_level=cli_args.trigger_level,
                )
