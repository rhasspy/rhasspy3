#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

from pyaudio_shared import iter_chunks

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rate", type=int, required=True, help="Sample rate (hertz)")
    parser.add_argument("--width", type=int, required=True, help="Sample width (bytes)")
    parser.add_argument(
        "--channels", type=int, required=True, help="Sample channel count"
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        required=True,
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
        sys.stdout.buffer.write(chunk)


if __name__ == "__main__":
    main()
