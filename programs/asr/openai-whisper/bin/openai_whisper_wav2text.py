#!/usr/bin/env python3
import argparse
import logging
import time
from pathlib import Path

import openai

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("api_key_path", help="Path to OpenAI API key")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    parser.add_argument("--model", default="whisper-1", help="Model name to use")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    openai.api_key_path = args.api_key_path

    # Load converted faster-whisper model
    for wav_path in args.wav_file:
        _LOGGER.debug("Processing %s", wav_path)
        start_time = time.monotonic_ns()
        audio_file = open(wav_path, "rb")
        text = openai.Audio.transcribe(args.model, audio_file).text
        audio_file.close()
        end_time = time.monotonic_ns()
        _LOGGER.debug(
            "Transcribed %s in %s second(s)", wav_path, (end_time - start_time) / 1e9
        )
        _LOGGER.debug(text)

        print(text, flush=True)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
