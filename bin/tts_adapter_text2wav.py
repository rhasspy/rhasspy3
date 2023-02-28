#!/usr/bin/env python3
"""
Runs a text to speech command that returns WAV audio on stdout or in a temp file.
"""
import argparse
import io
import logging
import shlex
import subprocess
import tempfile
import wave
from pathlib import Path

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.tts import Synthesize

_LOGGER = logging.getLogger("tts_adapter_text2wav")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument(
        "--temp_file",
        action="store_true",
        help="Command has {temp_file} and will write output to it",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Command has {text} argument",
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

                write_event(AudioStart(rate, width, channels, timestamp=0).event())
                write_event(
                    AudioChunk(rate, width, channels, audio_bytes, timestamp=0).event()
                )
                write_event(AudioStop(timestamp=timestamp).event())
    except KeyboardInterrupt:
        pass


def text_to_wav(args: argparse.Namespace, text: str) -> bytes:
    command_str = args.command
    format_args = {}
    if args.text:
        format_args["text"] = text
        text = ""  # Pass as arg instead

    if args.temp_file:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".wav") as wav_file:
            format_args["temp_file"] = wav_file.name
            command_str = command_str.format(**format_args)
            command = shlex.split(command_str)

            # Send stdout to devnull so it doesn't interfere with our events
            subprocess.run(
                command, check=True, stdout=subprocess.DEVNULL, input=text.encode()
            )
            wav_file.seek(0)
            return Path(wav_file.name).read_bytes()

    else:
        command_str = command_str.format(**format_args)
        command = shlex.split(command_str)
        return subprocess.check_output(command, input=text.encode())


if __name__ == "__main__":
    main()
