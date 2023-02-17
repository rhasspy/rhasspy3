#!/usr/bin/env python3
import argparse
import logging
import platform
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")

PLATFORMS = {"x86_64": "amd64", "aarch64": "arm64"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        help="CPU architecture to download (amd64, arm64)",
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: lib)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/models/releases/download/v1.0/libwhisper_{platform}.tar.gz",
        help="Format string for download URLs",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if not args.platform:
        args.platform = platform.machine()

    args.platform = PLATFORMS.get(args.platform, args.platform)

    if not args.destination:
        args.destination = _DIR.parent / "lib"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    url = args.link_format.format(platform=args.platform)
    _LOGGER.info("Downloading %s", url)
    with urlopen(url) as response:
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            _LOGGER.info("Extracting to %s", args.destination)
            tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
