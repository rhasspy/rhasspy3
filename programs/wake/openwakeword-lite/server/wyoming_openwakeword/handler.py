"""Event handler for clients of the server."""
import argparse
import logging
import time
import wave
from pathlib import Path
from typing import Final, Optional

import numpy as np

from wyoming.audio import AudioChunk, AudioChunkConverter, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Describe, Info
from wyoming.server import AsyncEventHandler
from wyoming.wake import NotDetected

from .const import ClientData, WakeWordData
from .state import State

_LOGGER = logging.getLogger(__name__)
_NS_SAMPLES: Final = 320
_NS_BYTES: Final = _NS_SAMPLES * 2


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
        self.is_detected = False
        self.converter = AudioChunkConverter(rate=16000, width=2, channels=1)
        self.audio_buffer = bytes()

        # Only used when output_dir is set
        self.audio_writer: Optional[wave.Wave_write] = None

        # Noise suppression using speexdsp
        self.noise_supression: "Optional[NoiseSuppression]" = None
        if self.cli_args.noise_suppression:
            _LOGGER.debug("Noise suppression enabled")
            from speexdsp_ns import NoiseSuppression

            self.noise_supression = NoiseSuppression.create(_NS_SAMPLES, 16000)

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

        if AudioStart.is_type(event.type):
            # Reset
            self.is_detected = False
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

            if self.noise_supression is None:
                # No noise suppression
                clean_audio = chunk.audio
                chunk_array = np.frombuffer(clean_audio, dtype=np.int16).astype(
                    np.float32
                )
            else:
                # Noise suppression
                self.audio_buffer += chunk.audio
                num_ns_chunks = len(self.audio_buffer) // _NS_BYTES
                if num_ns_chunks <= 0:
                    # No enough audio for noise suppression
                    return True

                clean_audio = bytes()
                for ns_chunk_idx in range(num_ns_chunks):
                    ns_chunk_offset = ns_chunk_idx * _NS_BYTES
                    clean_audio += self.noise_supression.process(
                        self.audio_buffer[
                            ns_chunk_offset : (ns_chunk_offset + _NS_BYTES)
                        ]
                    )

                # Remove processed audio
                self.audio_buffer = self.audio_buffer[num_ns_chunks * _NS_BYTES :]

                # Use clean audio
                chunk_array = np.frombuffer(clean_audio, dtype=np.int16).astype(
                    np.float32
                )

            if self.audio_writer is not None:
                self.audio_writer.writeframes(clean_audio)

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
            if not self.is_detected:
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
