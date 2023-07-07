#!/usr/bin/env python3
"""Record a spoken audio sample to a WAV file."""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from rhasspy3.audio import (
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
    AudioChunk,
    AudioChunkConverter,
)
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process, AsyncNullContextManager

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument(
        "-p", "--pipeline", default="default", help="Name of pipeline to use"
    )
    parser.add_argument(
        "--mic-program", help="Name of mic program to use (overrides pipeline)"
    )
    parser.add_argument(
        "--mic-filter", help="Name of mic filter program to use (overrides pipeline)"
    )
    #
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
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"

    converter = AudioChunkConverter(
        rate=args.rate, width=args.width, channels=args.channels
    )

    has_filter = bool(args.mic_filter)
    if has_filter:
        filter_proc = await create_process(rhasspy, "mic_filter", args.mic_filter)
        assert filter_proc.proc.stdin is not None
        assert filter_proc.proc.stdout is not None
    else:
        filter_proc = AsyncNullContextManager()

    async with (
        await create_process(rhasspy, MIC_DOMAIN, mic_program)
    ) as mic_proc, filter_proc:
        assert mic_proc.stdout is not None
        while True:
            mic_event = await async_read_event(mic_proc.stdout)
            if mic_event is None:
                break

            if not AudioChunk.is_type(mic_event.type):
                continue

            chunk = AudioChunk.from_event(mic_event)
            if has_filter:
                filter_proc.proc.stdin.write(chunk.audio)
                await filter_proc.proc.stdin.drain()
                filtered_audio = await filter_proc.proc.stdout.readexactly(
                    len(chunk.audio)
                )
                chunk = AudioChunk(
                    rate=chunk.rate,
                    width=chunk.width,
                    channels=chunk.channels,
                    audio=filtered_audio,
                    timestamp=chunk.timestamp,
                )

            chunk = converter.convert(chunk)
            sys.stdout.buffer.write(chunk.audio)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
