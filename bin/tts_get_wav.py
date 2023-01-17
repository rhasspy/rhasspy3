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
from urllib.parse import urlencode
from urllib.request import urlopen

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.tts import Synthesize
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("tts_get_wav")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="URL of API endpoint",
    )
    parser.add_argument(
        "--param",
        nargs=2,
        action="append",
        metavar=("name", "value"),
        help="Name/value of query parameter",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.param:
        params = dict(args.param)
    else:
        params = {}

    try:
        while True:
            event = read_event()
            if event is None:
                break

            if Synthesize.is_type(event.type):
                synthesize = Synthesize.from_event(event)

                params["text"] = synthesize.text
                url = args.url + "?" + urlencode(params)

                with urlopen(url) as response:
                    with wave.open(response, "rb") as wav_file:
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


if __name__ == "__main__":
    main()
