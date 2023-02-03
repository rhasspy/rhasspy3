#!/usr/bin/env python3
"""Reads raw audio chunks from stdin."""
import argparse
import logging
import shlex
import subprocess
import time
from pathlib import Path

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
    AudioStart,
)
from rhasspy3.event import write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Number of samples to read at a time from command",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=DEFAULT_IN_RATE,
        help="Sample rate (hz)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_IN_WIDTH,
        help="Sample width bytes",
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_IN_CHANNELS,
        help="Sample channel count",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * args.width * args.channels

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(command, stdout=subprocess.PIPE)
    with proc:
        assert proc.stdout is not None

        write_event(
            AudioStart(
                args.rate, args.width, args.channels, timestamp=time.monotonic_ns()
            ).event()
        )
        while True:
            audio_bytes = proc.stdout.read(bytes_per_chunk)
            if not audio_bytes:
                break

            write_event(
                AudioChunk(
                    args.rate,
                    args.width,
                    args.channels,
                    audio_bytes,
                    timestamp=time.monotonic_ns(),
                ).event()
            )


if __name__ == "__main__":
    main()
