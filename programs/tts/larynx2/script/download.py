#!/usr/bin/env python3
import argparse
import logging
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "language",
        nargs="+",
        choices=("english", "danish", "german", "nepali", "norwegian", "vietnamese"),
        help="Voice language(s) to download",
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: share)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/larynx2/releases/download/v0.0.2/voice-{language}.tar.gz",
        help="Format string for download URLs",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/tts/larynx2/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "tts" / "larynx2"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    for language in args.language:
        url = args.link_format.format(language=language)
        _LOGGER.info("Downloading %s", url)
        with urlopen(url) as response:
            with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
                _LOGGER.info("Extracting to %s", args.destination)
                tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
