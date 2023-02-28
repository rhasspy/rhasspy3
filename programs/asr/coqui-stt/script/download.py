#!/usr/bin/env python3
import argparse
import itertools
import logging
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")

MODELS = {"en_large": "english_v1.0.0-large-vocab"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "model",
        nargs="+",
        choices=list(itertools.chain(MODELS.keys(), MODELS.values())),
        help="Coqui STT model(s) to download",
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: share)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/models/releases/download/v1.0/asr_coqui-stt-{model}.tar.gz",
        help="Format string for download URLs",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/asr/coqui-stt/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "asr" / "coqui-stt"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    for model in args.model:
        model = MODELS.get(model, model)
        url = args.link_format.format(model=model)
        _LOGGER.info("Downloading %s", url)
        with urlopen(url) as response:
            with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
                _LOGGER.info("Extracting to %s", args.destination)
                tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
