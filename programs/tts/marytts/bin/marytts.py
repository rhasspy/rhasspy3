#!/usr/bin/env python3
import argparse
import logging
import shutil
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="URL of API endpoint",
    )
    parser.add_argument("voice", help="VOICE parameter")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    params = {"INPUT_TEXT": sys.stdin.read(), "VOICE": args.voice}
    url = args.url + "?" + urlencode(params)

    _LOGGER.debug(url)

    with urlopen(url) as response:
        shutil.copyfileobj(response, sys.stdout.buffer)


if __name__ == "__main__":
    main()
