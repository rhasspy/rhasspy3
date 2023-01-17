#!/usr/bin/env python3
import argparse
import logging
import shutil
import sys
from urllib.parse import urlencode
from urllib.request import urlopen

_LOGGER = logging.getLogger("marytts")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="URL of API endpoint",
    )
    parser.add_argument("voice", help="VOICE parameter")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    params = {"INPUT_TEXT": sys.stdin.read(), "VOICE": args.voice}
    url = args.url + "?" + urlencode(params)

    with urlopen(url) as response:
        shutil.copyfileobj(response, sys.stdout.buffer)


if __name__ == "__main__":
    main()
