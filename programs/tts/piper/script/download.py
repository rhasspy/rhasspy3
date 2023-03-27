#!/usr/bin/env python3
import argparse
import logging
import tarfile
from pathlib import Path
from urllib.request import urlopen

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger("setup")

_VOICES = {
    "catalan": "ca",
    "ca": "ca_upc_ona",
    "ca_upc_ona": "ca_upc_ona",
    "ca_upc_pau": "ca_upc_pau",
    #
    "danish": "da",
    "da": "da_nst_talesynthese",
    "da_nst_talesynthese": "da_nst_talesyntese",
    #
    "german": "de",
    "de": "de_thorsten",
    "de_thorsten": "de_thorsten",
    "de_eva_k": "de_eva_k",
    #
    "english": "en-us",
    "en-us": "en-us_lessac",
    "en-us_lessac": "en-us_lessac",
    "en-us_ljspeech": "en-us_ljspeech",
    "en-us_ryan": "en-us_ryan",
    #
    "spanish": "es",
    "es": "es_carlfm",
    "es_carlfm": "es_carlfm",
    #
    "french": "fr",
    "fr": "fr_siwis",
    "fr_siwis": "fr_siwis",
    #
    "italian": "it",
    "it": "it_riccardo_fasol",
    "it_riccardo_fasol": "it_riccardo_fasol",
    #
    "kazakh": "kk",
    "kk": "kk_iseke",
    "kk_iseke": "kk_iseke",
    "kk_raya": "kk_raya",
    #
    "nepali": "ne",
    "ne": "ne_google",
    "ne_google": "ne_google",
    #
    "dutch": "nl",
    "nl": "nl_rdh",
    "nl_rdh": "nl_rdh",
    "nl_nathalie": "nl_nathalie",
    #
    "norwegian": "no",
    "no": "no_talesynthese",
    "no_talesynthese": "no_talesynthese",
    #
    "ukrainian": "uk",
    "uk": "uk_lada",
    "uk_lada": "uk_lada",
    #
    "vietnamese": "vi",
    "vi": "vi_vivos",
    "vi_vivos": "vi_vivos",
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    if args.destination:
        args.destination = Path(args.destination)
    else:
        # Assume we're in programs/tts/piper/script
        data_dir = _DIR.parent.parent.parent.parent / "data"
        args.destination = data_dir / "tts" / "piper"

    args.destination.parent.mkdir(parents=True, exist_ok=True)

    for name in args.name:
        resolved_name = _VOICES[name]
        while resolved_name != name:
            name = resolved_name
            resolved_name = _VOICES[name]

        url = args.link_format.format(name=name)
        _LOGGER.info("Downloading %s", url)
        with urlopen(url) as response:
            with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
                _LOGGER.info("Extracting to %s", args.destination)
                tar_gz.extractall(args.destination)


if __name__ == "__main__":
    main()
