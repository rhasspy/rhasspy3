#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

import webrtcvad

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=(0, 1, 2, 3),
        type=int,
        help="Aggressiveness in filtering out non-speech",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=16000,
        help="Sample rate (hz)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=2,
        help="Sample width bytes",
    )
    parser.add_argument("--samples-per-chunk", type=int, default=480)
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    chunk_ms = 1000 * (args.samples_per_chunk / args.rate)
    assert chunk_ms in [10, 20, 30], (
        "Sample rate and chunk size must make for 10, 20, or 30 ms buffer sizes,"
        + f" assuming mono audio (got {chunk_ms} ms)"
    )

    bytes_per_chunk = args.samples_per_chunk * args.width
    vad = webrtcvad.Vad()
    vad.set_mode(args.mode)

    try:
        chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while chunk:
            speech_probability = 1 if vad.is_speech(chunk, args.rate) else 0
            print(speech_probability, flush=True)
            chunk = sys.stdin.buffer.read(bytes_per_chunk)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
