#!/usr/bin/env python3
import argparse
import asyncio
import logging
import struct
from functools import partial
from pathlib import Path

from porcupine_shared import get_arg_parser, load_porcupine

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.event import Event
from rhasspy3.wake import Detection, NotDetected
from wyoming.info import Attribution, Describe, Info, WakeModel, WakeProgram
from wyoming.server import AsyncEventHandler, AsyncServer

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


class PorcupineEventHandler(AsyncEventHandler):
    def __init__(
        self,
        cli_args: argparse.Namespace,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args

        self._porcupine, self._keyword_names = load_porcupine(self.cli_args)
        self.wyoming_info_event = Info(
            wake=[
                WakeProgram(
                    name="porcupine1",
                    description="Porcupine version 1",
                    attribution=Attribution(
                        name="Picovoice",
                        url="https://github.com/Picovoice/porcupine",
                    ),
                    installed=True,
                    models=[
                        WakeModel(
                            name=keyword,
                            description=keyword,
                            attribution=Attribution(
                                name=keyword,
                                url="https://github.com/Picovoice/porcupine",
                            ),
                            installed=True,
                            languages=[],
                        )
                        for keyword in self._keyword_names
                    ],
                )
            ]
        ).event()

        self._chunk_format = "h" * self._porcupine.frame_length
        self._bytes_per_chunk = self._porcupine.frame_length * 2  # 16-bit width
        self._audio_bytes = bytes()
        self._is_detected = False

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self.wyoming_info_event)
            _LOGGER.debug("Sent info")
            return True

        if AudioStop.is_type(event.type):
            if not self._is_detected:
                await self.write_event(NotDetected().event())

            return False

        if not AudioChunk.is_type(event.type):
            return True

        chunk = AudioChunk.from_event(event)
        self._audio_bytes += chunk.audio

        while len(self._audio_bytes) >= self._bytes_per_chunk:
            unpacked_chunk = struct.unpack_from(
                self._chunk_format, self._audio_bytes[: self._bytes_per_chunk]
            )
            keyword_index = self._porcupine.process(unpacked_chunk)
            if keyword_index >= 0:
                keyword_name = self._keyword_names[keyword_index]
                _LOGGER.debug("Triggered: %s", keyword_name)
                await self.write_event(
                    Detection(
                        name=keyword_name,
                        timestamp=chunk.timestamp,
                    ).event()
                )
                self._is_detected = True

            self._audio_bytes = self._audio_bytes[self._bytes_per_chunk :]

        return True


# -----------------------------------------------------------------------------


async def main() -> None:
    """Main method."""
    parser = get_arg_parser()
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Start server
    server = AsyncServer.from_uri(args.uri)

    _LOGGER.info("Ready")
    await server.run(partial(PorcupineEventHandler, args))


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
