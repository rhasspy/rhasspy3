#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

from stt import Model
import numpy as np

_LOGGER = logging.getLogger("coqui_stt_server")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Coqui STT model directory")
    parser.add_argument(
        "--scorer", help="Path to scorer (default: .scorer file in model directory)"
    )
    parser.add_argument(
        "--alpha-beta",
        type=float,
        nargs=2,
        metavar=("alpha", "beta"),
        help="Scorer alpha/beta",
    )
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=16000,
        help="Input audio sample rate (default: 16000)",
    )
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
    model_path = next(model_dir.glob("*.tflite"))
    if args.scorer:
        scorer_path = Path(args.scorer)
    else:
        scorer_path = next(model_dir.glob("*.scorer"))

    _LOGGER.debug("Loading model: %s, scorer: %s", model_path, scorer_path)
    model = Model(str(model_path))
    model.enableExternalScorer(str(scorer_path))

    if args.alpha_beta is not None:
        model.setScorerAlphaBeta(*args.alpha_beta)

    model_stream = model.createStream()
    chunk = sys.stdin.buffer.read(args.samples_per_chunk)
    _LOGGER.debug("Processing audio")
    while chunk:
        chunk_array = np.frombuffer(chunk, dtype=np.int16)
        model_stream.feedAudioContent(chunk_array)
        chunk = sys.stdin.buffer.read(args.samples_per_chunk)

    text = model_stream.finishStream()
    _LOGGER.debug(text)

    print(text.strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
