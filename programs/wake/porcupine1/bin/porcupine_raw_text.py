#!/usr/bin/env python3
import argparse
import logging
import struct
import sys
from pathlib import Path

from porcupine_shared import get_arg_parser, load_porcupine

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = get_arg_parser()
    parser.add_argument("--samples-per-chunk", type=int, default=512)
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    porcupine, names = load_porcupine(args)

    chunk_format = "h" * porcupine.frame_length
    bytes_per_chunk = porcupine.frame_length * 2

    # Read 16Khz, 16-bit mono PCM from stdin
    try:
        chunk = bytes()
        next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while next_chunk:
            while len(chunk) >= bytes_per_chunk:
                unpacked_chunk = struct.unpack_from(
                    chunk_format, chunk[:bytes_per_chunk]
                )
                keyword_index = porcupine.process(unpacked_chunk)
                if keyword_index >= 0:
                    print(names[keyword_index], flush=True)

                chunk = chunk[bytes_per_chunk:]

            next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
            chunk += next_chunk
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
