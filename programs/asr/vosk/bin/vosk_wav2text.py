#!/usr/bin/env python3
import argparse
import json
import logging
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Vosk model directory")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
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

    for wav_path in args.wav_file:
        _LOGGER.debug("Processing %s", wav_path)
        wav_file: wave.Wave_read = wave.open(wav_path, "rb")
        with wav_file:
            assert wav_file.getframerate() == 16000, "16Khz sample rate required"
            assert wav_file.getsampwidth() == 2, "16-bit samples required"
            assert wav_file.getnchannels() == 1, "Mono audio required"
            audio_bytes = wav_file.readframes(wav_file.getnframes())
            recognizer.AcceptWaveform(audio_bytes)

            result = json.loads(recognizer.FinalResult())
            print(result["text"].strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
