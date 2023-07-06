#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

from precise_shared import get_arg_parser, load_precise

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = get_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    engine = load_precise(args)
    bytes_per_chunk = args.samples_per_chunk * 2  # 16-bit samples

    # Read 16Khz, 16-bit mono PCM from stdin
    try:
        chunk = bytes()
        next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while next_chunk:
            while len(chunk) >= bytes_per_chunk:
                engine.update(chunk[:bytes_per_chunk])
                if engine.found_wake_word(None):
                    print(args.model, flush=True)

                chunk = chunk[bytes_per_chunk:]

            next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
            chunk += next_chunk
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
