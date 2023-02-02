#!/usr/bin/env python3
"""Play audio through a command that accepts raw PCM."""
import argparse
import logging
import shlex
import subprocess

from rhasspy3.audio import AudioChunk, AudioChunkConverter
from rhasspy3.event import read_event

_LOGGER = logging.getLogger("snd_adapter_raw")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--rate", type=int, help="Sample rate (hertz)")
    parser.add_argument("--width", type=int, help="Sample width (bytes)")
    parser.add_argument("--channels", type=int, help="Sample channel count")
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    converter = AudioChunkConverter(args.rate, args.width, args.channels)
    while True:
        event = read_event()
        if event is None:
            break

        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            chunk = converter.convert(chunk)
            proc.stdin.write(chunk.audio)
            proc.stdin.flush()


if __name__ == "__main__":
    main()
