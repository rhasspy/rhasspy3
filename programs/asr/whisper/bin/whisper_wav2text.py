#!/usr/bin/env python3
import argparse
import logging

from whisper import load_model, transcribe

_LOGGER = logging.getLogger("whisper_wav2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Name of Whisper model to use")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    parser.add_argument(
        "--language",
        help="Whisper language",
    )
    parser.add_argument("--device", default="cpu", choices=("cpu", "cuda"))
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    _LOGGER.debug("Loading model: %s", args.model)
    model = load_model(args.model, device=args.device)
    for wav_file in args.wav_file:
        _LOGGER.debug("Processing %s", wav_file)
        result = transcribe(model, wav_file, language=args.language)
        _LOGGER.debug(result)

        text = result["text"]
        print(text.strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
