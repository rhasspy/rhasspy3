#!/usr/bin/env python3
"""Wait for wake word to be detected in a stream."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
)
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_get_stdin
from rhasspy3.wake import detect_stream

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
        "--wake-program", help="Name of wake program to use (overrides pipeline)"
    )
    #
    parser.add_argument(
        "--mic-rate",
        type=int,
        default=DEFAULT_IN_RATE,
        help="Input sample rate (hertz)",
    )
    parser.add_argument(
        "--mic-width",
        type=int,
        default=DEFAULT_IN_WIDTH,
        help="Input sample width (bytes)",
    )
    parser.add_argument(
        "--mic-channels",
        type=int,
        default=DEFAULT_IN_CHANNELS,
        help="Input sample channel count",
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Samples to process per chunk",
    )
    #
    parser.add_argument("--loop", action="store_true", help="Keep detecting wake words")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    wake_program = args.wake_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not wake_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        wake_program = pipeline.wake

    assert wake_program, "No wake program"
    _LOGGER.debug("wake program: %s", wake_program)

    # Detect wake word
    bytes_per_chunk = args.samples_per_chunk * args.mic_width * args.mic_channels
    stdin_reader = await async_get_stdin()

    async def audio_stream():
        while True:
            chunk = await stdin_reader.read(bytes_per_chunk)
            if not chunk:
                break
            yield chunk

    while True:
        _LOGGER.debug("Detecting wake word")
        detection = await detect_stream(
            rhasspy,
            wake_program,
            audio_stream(),
            rate=args.mic_rate,
            width=args.mic_width,
            channels=args.mic_channels,
        )
        if detection is not None:
            json.dump(detection.event().to_dict(), sys.stdout, ensure_ascii=False)
            print("", flush=True)

        if not args.loop:
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
