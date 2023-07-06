#!/usr/bin/env python3
"""Reads raw audio chunks from stdin."""
import argparse
import logging
import shlex
import subprocess
import threading
import time
from pathlib import Path

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
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
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    #
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Number of samples to read at a time from command",
    )
    parser.add_argument(
        "--rate",
        type=int,
        required=True,
        help="Sample rate (hz)",
    )
    parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Sample width bytes",
    )
    parser.add_argument(
        "--channels",
        type=int,
        required=True,
        help="Sample channel count",
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * args.width * args.channels

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(command, stdout=subprocess.PIPE)
    with proc:
        assert proc.stdout is not None

        stop_event = threading.Event()
        threading.Thread(target=wait_for_stop, daemon=True, args=(stop_event,)).start()

        write_event(
            AudioStart(
                args.rate, args.width, args.channels, timestamp=time.monotonic_ns()
            ).event()
        )

        try:
            while True:
                if stop_event.is_set():
                    break

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
        except KeyboardInterrupt:
            pass


def wait_for_stop(stop_event: threading.Event):
    try:
        while True:
            event = read_event()
            if event is None:
                break

            if AudioStop.is_type(event.type):
                stop_event.set()
                break
    except KeyboardInterrupt:
        pass
    except Exception:
        _LOGGER.exception("Unexpected error in wait_for_stop")


if __name__ == "__main__":
    main()
