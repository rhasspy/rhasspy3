#!/usr/bin/env python3
import argparse
import logging
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")

_VOICE_NAMES = [
    "ca-upc_ona-x-low",
    "ca-upc_pau-x-low",
    "da-nst_talesyntese-medium",
    "de-eva_k-x-low",
    "de-thorsten-low",
    "en-gb-alan-low",
    "en-gb-southern_english_female-low",
    "en-us-amy-low",
    "en-us-kathleen-low",
    "en-us-lessac-low",
    "en-us-lessac-medium",
    "en-us-libritts-high",
    "en-us-ryan-high",
    "en-us-ryan-low",
    "en-us-ryan-medium",
    "es-carlfm-x-low",
    "fi-harri-low",
    "fr-siwis-low",
    "fr-siwis-medium",
    "it-riccardo_fasol-x-low",
    "kk-iseke-x-low",
    "kk-issai-high",
    "kk-raya-x-low",
    "ne-google-medium",
    "ne-google-x-low",
    "nl-mls_7432-low",
    "nl-nathalie-x-low",
    "nl-rdh-medium",
    "nl-rdh-x-low",
    "no-talesyntese-medium",
    "pl-mls_6892-low",
    "pt-br-edresson-low",
    "uk-lada-x-low",
    "vi-25hours-single-low",
    "vi-vivos-x-low",
    "zh-cn-huayan-x-low",
]

_VOICES = {
    "catalan": "ca",
    "ca": "ca-upc_ona-x-low",
    #
    "danish": "da",
    "da": "da-nst_talesyntese-medium",
    #
    "german": "de",
    "de": "de-thorsten-low",
    #
    "english": "en",
    "en": "en-us",
    "en-us": "en-us-lessac-low",
    "en-gb": "en-gb-alan-low",
    #
    "spanish": "es",
    "es": "es-carlfm-x-low",
    #
    "french": "fr",
    "fr": "fr-siwis-low",
    #
    "italian": "it",
    "it": "it-riccardo_fasol-x-low",
    #
    "kazakh": "kk",
    "kk": "kk-iseke-x-low",
    #
    "nepali": "ne",
    "ne": "ne-google-x-low",
    #
    "dutch": "nl",
    "nl": "nl-rdh-x-low",
    #
    "norwegian": "no",
    "no": "no-talesyntese-medium",
    #
    "polish": "pl",
    "pl": "pl-mls_6892-low",
    #
    "portuguese": "pt",
    "pt": "pt-br",
    "pt-br": "pt-br-edresson-low",
    #
    "ukrainian": "uk",
    "uk": "uk-lada-x-low",
    #
    "vietnamese": "vi",
    "vi": "vi-25hours-single-low",
    #
    "chinese": "zh",
    "zh": "zh-cn",
    "zh-cn": "zh-cn-huayan-x-low",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "name",
        nargs="+",
        choices=sorted(_VOICES.keys()),
        help="Voice language(s) to download",
    )
    parser.add_argument(
        "--destination", help="Path to destination directory (default: share)"
    )
    parser.add_argument(
        "--link-format",
        default="https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{name}.tar.gz",
        help="Format string for download URLs",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually download"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/tts/piper/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "tts" / "piper"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    for voice_name in _VOICE_NAMES:
        _VOICES[voice_name] = voice_name

    for name in args.name:
        resolved_name = _VOICES[name]
        while resolved_name != name:
            name = resolved_name
            resolved_name = _VOICES[name]

        url = args.link_format.format(name=name)
        _LOGGER.info("Downloading %s", url)

        if args.dry_run:
            return

        with urlopen(url) as response:
            with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
                _LOGGER.info("Extracting to %s", args.destination)
                tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
