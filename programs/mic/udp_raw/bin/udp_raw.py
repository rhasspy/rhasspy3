#!/usr/bin/env python3
import argparse
import socketserver
from functools import partial

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    AudioChunk,
)
from rhasspy3.event import write_event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="0.0.0.0")
    #
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_IN_RATE, help="Sample rate (hertz)"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_IN_WIDTH, help="Sample width (bytes)"
    )
    parser.add_argument(
        "--channels",
        type=int,
        default=DEFAULT_IN_CHANNELS,
        help="Sample channel count",
    )
    args = parser.parse_args()

    with socketserver.UDPServer(
        (args.host, args.port),
        partial(MicUDPHandler, args.rate, args.width, args.channels),
    ) as server:
        server.serve_forever()


class MicUDPHandler(socketserver.BaseRequestHandler):
    def __init__(self, rate: int, width: int, channels: int, *args, **kwargs):
        self.rate = rate
        self.width = width
        self.channels = channels
        self.state = None
        super().__init__(*args, **kwargs)

    def handle(self):
        audio_bytes = self.request[0]
        write_event(
            AudioChunk(
                rate=self.rate,
                width=self.width,
                channels=self.channels,
                audio=audio_bytes,
            ).event()
        )


if __name__ == "__main__":
    main()
