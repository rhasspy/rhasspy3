#!/usr/bin/env python3
import argparse
import logging
import shlex
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from rhasspy3.audio import AudioChunk
from rhasspy3.wake import Detection
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("wrapper_wake_print")


@dataclass
class State:
    timestamp: int = 0
    detected: bool = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    command = shlex.split(args.command)
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        assert proc.stdout is not None

        state = State()
        threading.Thread(target=write_proc, args=(proc.stdout, state)).start()

        while True:
            event = read_event()
            if event is None:
                break


            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                state.timestamp = (
                    chunk.timestamp if chunk.timestamp is not None else time.monotonic_ns()
                )
                proc.stdin.write(chunk.audio)
                proc.stdin.flush()
    finally:
        proc.terminate()


def write_proc(reader: IO[bytes], state: State):
    try:
        for line in reader:
            line = line.strip()
            if line:
                write_event(Detection(name=line.decode()).event())
                state.detected = True
                break
    except Exception:
        _LOGGER.exception("Unexpected error in write thread")


if __name__ == "__main__":
    main()
