#!/usr/bin/env python3
"""Prints configuration as JSON."""
import argparse
import json
import logging
import sys
from pathlib import Path

from rhasspy3.core import Rhasspy

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument("--indent", type=int, default=4)
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    json.dump(rhasspy.config_dict, sys.stdout, indent=args.indent, ensure_ascii=False)


if __name__ == "__main__":
    main()
