#!/usr/bin/env python3
import argparse
import audioop
import logging
import sys
from pathlib import Path

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Energy threshold above which is considered speech",
    )
    parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Sample width bytes",
    )
    parser.add_argument(
        "--samples-per-chunk",
        required=True,
        type=int,
        help="Samples to send to command at a time",
    )
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * args.width

    try:
        chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while chunk:
            energy = get_debiased_energy(chunk, args.width)
            speech_probability = 1 if energy > args.threshold else 0
            print(speech_probability, flush=True)
            chunk = sys.stdin.buffer.read(bytes_per_chunk)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


def get_debiased_energy(audio_data: bytes, width: int) -> float:
    """Compute RMS of debiased audio."""
    # Thanks to the speech_recognition library!
    # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
    energy = -audioop.rms(audio_data, width)
    energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
    debiased_energy = audioop.rms(
        audioop.add(audio_data, energy_bytes * (len(audio_data) // width), width),
        width,
    )

    return debiased_energy


if __name__ == "__main__":
    main()
