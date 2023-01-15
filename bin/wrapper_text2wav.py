#!/usr/bin/env python3
import argparse
import logging
import io
import shlex
import tempfile
import string
import subprocess
import wave
from pathlib import Path

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.tts import Synthesize
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("wrapper_text2wav")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument(
        "--temp_file",
        action="store_true",
        help="Command has ${temp_file} and will write output to it",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    try:
        while True:
            event = read_event()
            if event is None:
                break

            if Synthesize.is_type(event.type):
                synthesize = Synthesize.from_event(event)
                wav_bytes = text_to_wav(args, synthesize.text)
                with io.BytesIO(wav_bytes) as wav_io:
                    with wave.open(wav_io, "rb") as wav_file:
                        rate = wav_file.getframerate()
                        width = wav_file.getsampwidth()
                        channels = wav_file.getnchannels()

                        num_frames = wav_file.getnframes()
                        wav_seconds = num_frames / rate
                        timestamp = int(wav_seconds * 1_000)
                        audio_bytes = wav_file.readframes(num_frames)

                write_event(AudioStart(timestamp=0).event())
                write_event(
                    AudioChunk(rate, width, channels, audio_bytes, timestamp=0).event()
                )
                write_event(AudioStop(timestamp=timestamp).event())
    except KeyboardInterrupt:
        pass


def text_to_wav(args: argparse.Namespace, text: str) -> bytes:
    if args.temp_file:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".wav") as wav_file:
            template = string.Template(args.command)
            command_str = template.safe_substitute(temp_file=wav_file.name)
            command = shlex.split(command_str)
            subprocess.run(command, check=True, input=text.encode())
            wav_file.seek(0)
            return Path(wav_file.name).read_bytes()

    else:
        command = shlex.split(args.command)
        return subprocess.check_output(command, input=text.encode())


if __name__ == "__main__":
    main()
