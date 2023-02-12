#!/usr/bin/env python3
import argparse
import logging
import time
from pathlib import Path

from faster_whisper import WhisperModel

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to faster-whisper model directory")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device to use for inference (default: cpu)",
    )
    parser.add_argument(
        "--language",
        help="Language to set for transcription",
    )
    parser.add_argument(
        "--compute-type",
        default="default",
        help="Compute type (float16, int8, etc.)",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=1,
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Load converted faster-whisper model
    _LOGGER.debug("Loading model: %s", args.model)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)
    _LOGGER.info("Model loaded")

    for wav_path in args.wav_file:
        _LOGGER.debug("Processing %s", wav_path)
        start_time = time.monotonic_ns()
        segments, _info = model.transcribe(
            wav_path,
            beam_size=args.beam_size,
            language=args.language,
        )
        text = " ".join(segment.text for segment in segments)
        end_time = time.monotonic_ns()
        _LOGGER.debug(
            "Transcribed %s in %s second(s)", wav_path, (end_time - start_time) / 1e9
        )
        _LOGGER.debug(text)

        print(text, flush=True)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
