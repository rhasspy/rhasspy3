#!/usr/bin/env python3
import logging
import sys
from pathlib import Path

from oww_shared import get_arg_parser, load_openwakeword

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = get_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    oww_state = load_openwakeword(args)
    bytes_per_chunk = args.samples_per_chunk * 2  # 16-bit samples

    # Read 16Khz, 16-bit mono PCM from stdin
    try:
        chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while chunk:
            for ww_name, ww_probability in oww_state.predict(chunk).items():
                print(ww_name, flush=True)
                _LOGGER.debug("Triggered %s, probability=%s", ww_name, ww_probability)

            chunk = sys.stdin.buffer.read(bytes_per_chunk)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
