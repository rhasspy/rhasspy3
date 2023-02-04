#!/usr/bin/env python3
import argparse
import json
import logging
import sys

from vosk import KaldiRecognizer, Model, SetLogLevel

_LOGGER = logging.getLogger("vosk_raw2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Vosk model directory")
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=16000,
        help="Model sample rate (default: 16000)",
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=1024,
        help="Number of samples to process at a time",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    SetLogLevel(0)

    model = Model(args.model)
    recognizer = KaldiRecognizer(
        model,
        args.rate,
    )

    chunk = sys.stdin.buffer.read(args.samples_per_chunk)
    _LOGGER.debug("Processing audio")
    while chunk:
        recognizer.AcceptWaveform(chunk)
        chunk = sys.stdin.buffer.read(args.samples_per_chunk)

    result = json.loads(recognizer.FinalResult())
    print(result["text"].strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
