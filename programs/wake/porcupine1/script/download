#!/usr/bin/env python3
import argparse
import logging
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("download")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination", help="Path to destination directory (default: data)"
    )
    parser.add_argument(
        "--url",
        default="https://github.com/rhasspy/models/releases/download/v1.0/wake_porcupine1-data.tar.gz",
        help="URL of porcupine1 data",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/wake/porcupine1/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "wake" / "porcupine1"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    _LOGGER.info("Downloading %s", args.url)
    with urlopen(args.url) as response:
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            _LOGGER.info("Extracting to %s", args.destination)
            tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
