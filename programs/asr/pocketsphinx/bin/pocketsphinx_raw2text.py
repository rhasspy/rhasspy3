#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

import pocketsphinx

_LOGGER = logging.getLogger("pocketsphinx_raw2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Pocketsphinx model directory")
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=1024,
        help="Number of samples to process at a time",
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    model_dir = Path(args.model)

    _LOGGER.debug("Loading model from %s", model_dir.absolute())
    decoder_config = pocketsphinx.Decoder.default_config()
    decoder_config.set_string("-hmm", str(model_dir / "acoustic_model"))
    decoder_config.set_string("-dict", str(model_dir / "dictionary.txt"))
    decoder_config.set_string("-lm", str(model_dir / "language_model.txt"))
    decoder = pocketsphinx.Decoder(decoder_config)

    decoder.start_utt()

    chunk = sys.stdin.buffer.read(args.samples_per_chunk)
    _LOGGER.debug("Processing audio")
    while chunk:
        decoder.process_raw(chunk, False, False)
        chunk = sys.stdin.buffer.read(args.samples_per_chunk)

    decoder.end_utt()
    hyp = decoder.hyp()
    if hyp:
        text = hyp.hypstr
    else:
        text = ""

    _LOGGER.debug(text)

    print(text.strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
