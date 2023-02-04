#!/usr/bin/env python3
import argparse
import audioop
import logging
import wave
from pathlib import Path

import numpy as np
from whisper_cpp import Whisper

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to whisper.cpp model file")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    _LOGGER.debug("Loading model: %s", args.model)

    with Whisper(args.model) as whisper:
        for wav_path in args.wav_file:
            wav_file: wave.Wave_read = wave.open(wav_path, "rb")
            with wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()
                audio_bytes = wav_file.readframes(wav_file.getnframes())

                if width != 2:
                    audio_bytes = audioop.lin2lin(audio_bytes, width, 2)

                if channels != 1:
                    audio_bytes = audioop.tomono(audio_bytes, 2, 1.0, 1.0)

                if rate != 16000:
                    audio_bytes, _state = audioop.ratecv(
                        audio_bytes, 2, 1, rate, 16000, None
                    )

                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0

                text = " ".join(whisper.transcribe(audio_array))
                print(text)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
