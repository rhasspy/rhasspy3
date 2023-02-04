#!/usr/bin/env python3
import argparse
import socket

from rhasspy3.audio import (
    DEFAULT_OUT_CHANNELS,
    DEFAULT_OUT_RATE,
    DEFAULT_OUT_WIDTH,
    AudioChunk,
    AudioChunkConverter,
    AudioStop,
)
from rhasspy3.event import read_event, write_event
from rhasspy3.snd import Played


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", required=True)
    #
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
    #
    args = parser.parse_args()

    converter = AudioChunkConverter(args.rate, args.width, args.channels)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        event = read_event()
        if event is None:
            break

        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            chunk = converter.convert(chunk)
            sock.sendto(chunk.audio, (args.host, args.port))
        elif AudioStop.is_type(event.type):
            break

    write_event(Played().event())


if __name__ == "__main__":
    main()
