#!/usr/bin/env python3
import argparse
import logging
import shlex
import subprocess
import time
from pathlib import Path

from rhasspy3.audio import AudioChunk
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("wrapper_raw_snd")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    while True:
        event = read_event()
        if event is None:
            break

        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            proc.stdin.write(chunk.audio)
            proc.stdin.flush()


if __name__ == "__main__":
    main()
