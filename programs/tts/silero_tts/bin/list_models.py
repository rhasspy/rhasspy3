#!/usr/bin/env python3
import logging
import tempfile
from pathlib import Path

import torch
from omegaconf import OmegaConf

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("list_models")


def main() -> None:
    """Main method."""
    with tempfile.NamedTemporaryFile() as latest_silero_models:
        torch.hub.download_url_to_file('https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml',
                                       latest_silero_models.name,
                                       progress=False)
        models = OmegaConf.load(latest_silero_models.name)

    available_languages = list(models.tts_models.keys())
    print(f'Available languages {available_languages}')

    for lang in available_languages:
        _models = list(models.tts_models.get(lang).keys())
        print(f'Available models for {lang}: {_models}')


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
