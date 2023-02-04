#!/usr/bin/env python3
import argparse
import audioop
import socketserver

from rhasspy3.audio import AudioChunk
from rhasspy3.event import write_event


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    with socketserver.UDPServer((args.host, args.port), MicUDPHandler) as server:
        server.serve_forever()


class MicUDPHandler(socketserver.BaseRequestHandler):
    def __init__(self, *args, **kwargs):
        self.state = None
        super().__init__(*args, **kwargs)

    def handle(self):
        audio_bytes = self.request[0]
        audio_bytes, self.state = audioop.ratecv(
            audio_bytes, 2, 1, 22050, 16000, self.state
        )
        write_event(
            AudioChunk(rate=16000, width=2, channels=1, audio=audio_bytes).event()
        )


if __name__ == "__main__":
    main()
