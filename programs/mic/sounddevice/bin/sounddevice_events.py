#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from sounddevice_shared import iter_chunks

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
)
from rhasspy3.event import write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_IN_RATE, help="Sample rate (hertz)"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_IN_WIDTH, help="Sample width (bytes)"
    )
    parser.add_argument(
        "--channels", type=int, default=DEFAULT_IN_CHANNELS, help="Sample channel count"
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

    for chunk in iter_chunks(
        args.device, args.rate, args.width, args.channels, args.samples_per_chunk
    ):
        write_event(AudioChunk(args.rate, args.width, args.channels, chunk).event())


if __name__ == "__main__":
    main()
