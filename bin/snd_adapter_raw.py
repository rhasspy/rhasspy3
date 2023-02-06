#!/usr/bin/env python3
"""Play audio through a command that accepts raw PCM."""
import argparse
import logging
import shlex
import subprocess
from pathlib import Path

from rhasspy3.audio import (
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
    AudioChunk,
    AudioChunkConverter,
    AudioStop,
)
from rhasspy3.event import read_event, write_event
from rhasspy3.snd import Played

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
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
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    converter = AudioChunkConverter(args.rate, args.width, args.channels)
    with proc:
        while True:
            event = read_event()
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                chunk = converter.convert(chunk)
                proc.stdin.write(chunk.audio)
                proc.stdin.flush()
            elif AudioStop.is_type(event.type):
                break

    write_event(Played().event())


if __name__ == "__main__":
    main()
