#!/usr/bin/env python3
import argparse
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

    with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as wav_io:
        args.command = args.command.format(wav_file=shlex.quote(wav_io.name))
        if args.shell:
            command = args.command
        else:
            command = shlex.split(args.command)

        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        with wav_file:
            while True:
                event = read_event()
                if event is None:
                    break

                if AudioStart.is_type(event.type):
                    start = AudioStart.from_event(event)
                    wav_file.setframerate(start.rate)
                    wav_file.setsampwidth(start.width)
                    wav_file.setnchannels(start.channels)
                elif AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    wav_file.writeframes(chunk.audio)
                elif AudioStop.is_type(event.type):
                    break

        wav_io.seek(0)
        text = subprocess.check_output(command, shell=args.shell).decode()
        write_event(Transcript(text=text.strip()).event())


if __name__ == "__main__":
    main()
