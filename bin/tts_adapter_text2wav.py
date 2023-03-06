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

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.tts import Synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


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
    #
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

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
                        audio_bytes = wav_file.readframes(num_frames)

                bytes_per_chunk = args.samples_per_chunk * width
                timestamp = 0
                write_event(
                    AudioStart(rate, width, channels, timestamp=timestamp).event()
                )
                while audio_bytes:
                    chunk = AudioChunk(
                        rate,
                        width,
                        channels,
                        audio_bytes[:bytes_per_chunk],
                        timestamp=timestamp,
                    )
                    write_event(chunk.event())
                    timestamp += chunk.milliseconds
                    audio_bytes = audio_bytes[bytes_per_chunk:]

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
