#!/usr/bin/env python3
import argparse
import logging
import re
import subprocess
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("download")


def get_models():
    _LOGGER.info("Downloading list of models...")
    url = "https://github.com/MycroftAI/Precise-Community-Data.git/branches/master"
    url2 = "https://github.com/MycroftAI/Precise-Community-Data/raw/master/"
    filelist = subprocess.run(["svn", "ls", "-R", url], capture_output=True)
    result = {}
    for file in [x.decode() for x in filelist.stdout.split(b'\n')]:
        if not file.endswith('.tar.gz') or not "/models/" in file:
            continue
        result.update({re.split('[0-9]', file)[0].split('/')[-1].removesuffix('-'): url2 + file})
    return result

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination", help="Path to destination directory (default: data)"
    )
    parser.add_argument(
        "--name",
        help="Model name",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/wake/mycroft_precise/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "wake" / "mycroft_precise"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    models = get_models()
    if args.name is None or args.name not in models:
        _LOGGER.info("Available models: %s", list(models.keys()))
        return

    _LOGGER.info("Downloading %s", args.name)
    _LOGGER.info("URL: %s", models[args.name])
    with urlopen(models[args.name]) as response:
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            _LOGGER.info("Extracting to %s", args.destination)
            tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
