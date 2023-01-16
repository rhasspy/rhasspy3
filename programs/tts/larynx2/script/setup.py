#!/usr/bin/env python3
import argparse
import logging
import platform
import shutil
import tarfile
import tempfile
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
        "--destination", help="Path to destination directory (default: bin)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/larynx2/releases/download/v0.0.2/larynx_{platform}.tar.gz",
        help="Format string for download URLs",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if not args.platform:
        args.platform = platform.machine()

    args.platform = PLATFORMS.get(args.platform, args.platform)

    if not args.destination:
        args.destination = _DIR.parent / "bin"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    url = args.link_format.format(platform=args.platform)
    _LOGGER.info("Downloading %s", url)
    with urlopen(url) as response, tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            _LOGGER.info("Extracting to %s", temp_dir)
            tar_gz.extractall(temp_dir)

        # Move larynx/ contents
        larynx_dir = temp_dir / "larynx"
        for path in larynx_dir.iterdir():
            rel_path = path.relative_to(larynx_dir)
            if path.is_dir():
                shutil.copytree(path, args.destination / rel_path, symlinks=True)
            else:
                shutil.copy(path, args.destination / rel_path, follow_symlinks=False)


if __name__ == "__main__":
    main()
