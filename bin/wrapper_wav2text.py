#!/usr/bin/env python3
import argparse
import logging
import io
import shlex
import tempfile
import subprocess
import wave
from pathlib import Path

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.asr import Transcript
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("wrapper_wav2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--text-filter")
    parser.add_argument("--text-filter-shell", action="store_true")
    parser.add_argument(
        "--temp_file",
        action="store_true",
        help="Command has {temp_file} and will read input from it",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    try:
        if args.temp_file:
            with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as wav_io:
                args.command = args.command.format(temp_file=shlex.quote(wav_io.name))
                if args.shell:
                    command = args.command
                else:
                    command = shlex.split(args.command)

                with wave.open(wav_io, "wb") as wav_file:
                    first_chunk = True
                    while True:
                        event = read_event()
                        if event is None:
                            break

                        if AudioChunk.is_type(event.type):
                            chunk = AudioChunk.from_event(event)
                            if first_chunk:
                                wav_file.setframerate(chunk.rate)
                                wav_file.setsampwidth(chunk.width)
                                wav_file.setnchannels(chunk.channels)
                                first_chunk = False

                            wav_file.writeframes(chunk.audio)
                        elif AudioStop.is_type(event.type):
                            break

                wav_io.seek(0)
                text = subprocess.check_output(command, shell=args.shell).decode()
        else:
            if args.shell:
                command = args.command
            else:
                command = shlex.split(args.command)

            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, shell=args.shell
            )
            assert proc.stdin is not None
            assert proc.stdout is not None

            while True:
                event = read_event()
                if event is None:
                    break

                if AudioChunk.is_type(event):
                    chunk = AudioChunk.from_event(event)
                    proc.stdin.write(chunk.audio)
                    proc.stdin.flush()
                elif AudioStop.is_type(event):
                    break

            stdout, _stderr = proc.communicate()
            text = stdout.decode()

        if args.text_filter:
            if args.text_filter_shell:
                filter_command = args.text_filter
            else:
                filter_command = shlex.split(args.text_filter)

            text = subprocess.check_output(
                filter_command, input=text, shell=args.text_filter_shell, universal_newlines=True
            )

        write_event(Transcript(text=text.strip()).event())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
