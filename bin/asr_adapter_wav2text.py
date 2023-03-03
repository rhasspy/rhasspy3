#!/usr/bin/env python3
import argparse
import logging
import shlex
import subprocess
import tempfile
import wave
from pathlib import Path

from rhasspy3.asr import Transcript
from rhasspy3.audio import AudioChunk, AudioStop
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
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as wav_io:
        args.command = args.command.format(wav_file=wav_io.name)
        if args.shell:
            command = args.command
        else:
            command = shlex.split(args.command)

        wav_params_set = False
        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        try:
            with wav_file:
                while True:
                    event = read_event()
                    if event is None:
                        break

                    if AudioChunk.is_type(event.type):
                        chunk = AudioChunk.from_event(event)
                        if not wav_params_set:
                            wav_file.setframerate(chunk.rate)
                            wav_file.setsampwidth(chunk.width)
                            wav_file.setnchannels(chunk.channels)
                            wav_params_set = True

                        wav_file.writeframes(chunk.audio)
                    elif AudioStop.is_type(event.type):
                        break

            wav_io.seek(0)
            text = subprocess.check_output(command, shell=args.shell).decode()
            write_event(Transcript(text=text.strip()).event())
        except wave.Error:
            pass


if __name__ == "__main__":
    main()
