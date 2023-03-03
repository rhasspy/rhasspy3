#!/usr/bin/env python3
import argparse
import logging
import shlex
import subprocess
from pathlib import Path

from rhasspy3.asr import Transcript
from rhasspy3.audio import AudioChunk, AudioChunkConverter, AudioStop
from rhasspy3.event import read_event, write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    #
    parser.add_argument(
        "--rate",
        type=int,
        help="Sample rate (hz)",
    )
    parser.add_argument(
        "--width",
        type=int,
        help="Sample width bytes",
    )
    parser.add_argument(
        "--channels",
        type=int,
        help="Sample channel count",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=args.shell
    )
    text = ""
    converter = AudioChunkConverter(args.rate, args.width, args.channels)

    with proc:
        assert proc.stdin is not None
        assert proc.stdout is not None

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

        stdout, _stderr = proc.communicate()
        text = stdout.decode()

    write_event(Transcript(text=text.strip()).event())


if __name__ == "__main__":
    main()
