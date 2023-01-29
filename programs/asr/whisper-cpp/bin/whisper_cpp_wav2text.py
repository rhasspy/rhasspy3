#!/usr/bin/env python3
import argparse
import logging
import sys
import wave

import numpy as np
from whisper_cpp import Whisper

_LOGGER = logging.getLogger("whisper_cpp_raw2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to whisper.cpp model file")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    _LOGGER.debug("Loading model: %s", args.model)

    with Whisper(args.model) as whisper:
        for wav_path in args.wav_file:
            wav_file: wave.Wave_read = wave.open(wav_path, "rb")
            with wav_file:
                assert wav_file.getsampwidth() == 2
                assert wav_file.getnchannels() == 1
                audio_bytes = wav_file.readframes(wav_file.getnframes())
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0

                text = " ".join(whisper.transcribe(audio_array))
                print(text)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
