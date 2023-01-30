#!/usr/bin/env python3
import argparse
import logging
import itertools
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")

MODELS = {"en_medium": "en-us-0.22-lgraph", "en_small": "small-en-us-0.15"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model",
        nargs="+",
        choices=list(itertools.chain(MODELS.keys(), MODELS.values())),
        help="Vosk model(s) to download",
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: share)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/models/releases/download/v1.0/asr_vosk-model-{model}.zip",
        help="Format string for download URLs",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if not args.destination:
        args.destination = _DIR.parent / "share"

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
