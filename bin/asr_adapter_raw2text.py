#!/usr/bin/env python3
import argparse
import io
import logging
import shlex
import subprocess
import tempfile
import wave

from rhasspy3.asr import Transcript
from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger("asr_adapter_wav2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=args.shell
    )
    text = ""
    with proc:
        assert proc.stdin is not None
        assert proc.stdout is not None

        while True:
            event = read_event()
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                chunk = AudioChunk.from_event(event)
                proc.stdin.write(chunk.audio)
                proc.stdin.flush()
            elif AudioStop.is_type(event.type):
                break

        stdout, _stderr = proc.communicate()
        text = stdout.decode()

    write_event(Transcript(text=text.strip()).event())


if __name__ == "__main__":
    main()
