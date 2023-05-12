#!/usr/bin/env python3
import argparse
import logging
import tempfile
from pathlib import Path

import torch
from omegaconf import OmegaConf

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--language",
        help="Voice language to download",
        required=True
    )
    parser.add_argument(
        "--model",
        help="Model to download",
        required=True
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: share)"
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    with tempfile.NamedTemporaryFile() as latest_silero_models:
        torch.hub.download_url_to_file('https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml',
                                       latest_silero_models.name,
                                       progress=False)
        models = OmegaConf.load(latest_silero_models.name)

        if args.destination:
            data_path = Path(args.destination)
        else:
            data_path = _DIR.parent.parent.parent.parent / "data" / "tts" / "silero_tts" / "models"

        model_path = data_path / args.language

        model_path.mkdir(parents=True, exist_ok=True)

        torch.hub.download_url_to_file(models.tts_models[args.language][args.model].latest.package,
                                       model_path / f'{args.model}.pt')


if __name__ == "__main__":
    main()
