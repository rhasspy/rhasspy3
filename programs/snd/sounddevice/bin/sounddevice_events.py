#!/usr/bin/env python3
import argparse
import asyncio
import logging
from functools import partial
from pathlib import Path

import sounddevice as sd
from wyoming.server import AsyncServer, AsyncEventHandler

from rhasspy3.audio import (
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
    AudioChunkConverter,
    AudioStop,
)
from rhasspy3.event import Event
from rhasspy3.snd import Played

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


class SoundDeviceEventHandler(AsyncEventHandler):
    def __init__(
        self,
        cli_args: argparse.Namespace,
        stream: sd.RawOutputStream,
        converter: AudioChunkConverter,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.cli_args = cli_args
        self.stream = stream
        self.converter = converter

    async def handle_event(self, event: Event) -> bool:
        if AudioChunk.is_type(event.type):
            chunk = self.converter.convert(AudioChunk.from_event(event))
            self.stream.write(chunk.audio)
        elif AudioStop.is_type(event.type):
            await self.write_event(Played().event())
            return False

        return True


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_OUT_RATE, help="Sample rate (hertz)"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_OUT_WIDTH, help="Sample width (bytes)"
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_OUT_CHANNELS,
        help="Sample channel count",
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Number of samples to process at a time",
    )
    parser.add_argument("--device", help="Name or index of device to use")
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if not args.device:
        args.device = None  # default device

    converter = AudioChunkConverter(
        rate=args.rate, width=args.width, channels=args.channels
    )

    with sd.RawOutputStream(
        samplerate=args.rate,
        blocksize=args.samples_per_chunk,
        device=args.device,
        channels=args.channels,
        dtype="int16",
    ) as stream:
        # Start server
        server = AsyncServer.from_uri(args.uri)

        _LOGGER.info("Ready")
        await server.run(
            partial(
                SoundDeviceEventHandler,
                args,
                stream,
                converter,
            )
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
