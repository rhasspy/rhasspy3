#!/usr/bin/env python3
import argparse
import logging
import sys
import wave
from pathlib import Path

from stt import Model
import numpy as np

_LOGGER = logging.getLogger("coqui_stt_wav2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Coqui STT model directory")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
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

    for wav_path in args.wav_file:
        _LOGGER.debug("Processing %s", wav_path)
        wav_file: wave.Wave_read = wave.open(wav_path, "rb")
        with wav_file:
            assert wav_file.getframerate() == 16000, "16Khz sample rate required"
            assert wav_file.getsampwidth() == 2, "16-bit samples required"
            assert wav_file.getnchannels() == 1, "Mono audio required"
            audio_bytes = wav_file.readframes(wav_file.getnframes())

            model_stream = model.createStream()
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
            model_stream.feedAudioContent(audio_array)

            text = model_stream.finishStream()
            print(text.strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
