#!/usr/bin/env python3
import argparse
import logging
import wave
from pathlib import Path

import pocketsphinx


_LOGGER = logging.getLogger("pocketsphinx_wav2text")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Pocketsphinx model directory")
    parser.add_argument("wav_file", nargs="+", help="Path to WAV file(s) to transcribe")
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

    for wav_path in args.wav_file:
        _LOGGER.debug("Processing %s", wav_path)
        wav_file: wave.Wave_read = wave.open(wav_path, "rb")
        with wav_file:
            assert wav_file.getframerate() == 16000, "16Khz sample rate required"
            assert wav_file.getsampwidth() == 2, "16-bit samples required"
            assert wav_file.getnchannels() == 1, "Mono audio required"
            audio_bytes = wav_file.readframes(wav_file.getnframes())

            decoder.start_utt()
            decoder.process_raw(audio_bytes, False, True)
            decoder.end_utt()
            hyp = decoder.hyp()
            if hyp:
                text = hyp.hypstr
            else:
                text = ""

            print(text.strip())


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
