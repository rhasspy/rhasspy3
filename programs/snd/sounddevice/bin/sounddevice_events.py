#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

import sounddevice

from rhasspy3.audio import (
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
    AudioChunkConverter,
    AudioStop,
)
from rhasspy3.event import read_event, write_event
from rhasspy3.snd import Played

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_OUT_RATE, help="Sample rate (hertz)"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_OUT_WIDTH, help="Sample width (bytes)"
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_OUT_CHANNELS,
        help="Sample channel count",
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Number of samples to process at a time",
    )
    parser.add_argument("--device", help="Name or index of device to use")
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    converter = AudioChunkConverter(
        rate=args.rate, width=args.width, channels=args.channels
    )

    try:
        with sounddevice.RawOutputStream(
            samplerate=args.rate,
            blocksize=args.samples_per_chunk,
            device=args.device,
            channels=args.channels,
            dtype="int16",
        ) as stream:
            while True:
                event = read_event()
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    chunk = converter.convert(AudioChunk.from_event(event))
                    stream.write(chunk.audio)
                elif AudioStop.is_type(event.type):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        write_event(Played().event())


if __name__ == "__main__":
    main()
