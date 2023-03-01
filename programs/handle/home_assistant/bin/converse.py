#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from pathlib import Path
from urllib.request import Request, urlopen

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        help="URL of API endpoint",
    )
    parser.add_argument("token_file", help="Path to file with authorization token")
    parser.add_argument("--language", help="Language code to use")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    token = Path(args.token_file).read_text(encoding="utf-8").strip()
    headers = {"Authorization": f"Bearer {token}"}

    data_dict = {"text": sys.stdin.read()}
    if args.language:
        data_dict["language"] = args.language

    data = json.dumps(data_dict, ensure_ascii=False).encode("utf-8")
    request = Request(args.url, data=data, headers=headers)

    with urlopen(request) as response:
        response = json.loads(response.read())
        response_text = (
            response.get("response", {})
            .get("speech", {})
            .get("plain", {})
            .get("speech", "")
        )
        print(response_text)


if __name__ == "__main__":
    main()
