#!/usr/bin/env python3
import argparse
import logging
import wave
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.tts import Synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


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

    params = {}
    if args.param:
        for key, value in params.items():
            # Don't include empty parameters
            if value:
                params[key] = value

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


if __name__ == "__main__":
    main()
