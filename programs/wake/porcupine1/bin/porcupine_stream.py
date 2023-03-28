#!/usr/bin/env python3
import argparse
import logging
import struct
from pathlib import Path
from typing import List

import pvporcupine

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.wake import Detection, NotDetected

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        nargs="+",
        help="Keyword model settings (path, [sensitivity])",
    )
    parser.add_argument(
        "--lang_model",
        help="Path of the language model (.pv file), default is english one",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Path to embedded keywords
    keyword_dir = Path(next(iter(pvporcupine.pv_keyword_paths("").values()))).parent

    names: List[str] = []
    keyword_paths: List[Path] = []
    sensitivities: List[float] = []
    for model_settings in args.model:
        keyword_path_str = model_settings[0]
        keyword_path = Path(keyword_path_str)
        if not keyword_path.exists():
            keyword_path = keyword_dir / keyword_path_str
            assert keyword_path.exists(), f"Cannot find {keyword_path_str}"

        keyword_paths.append(keyword_path)
        names.append(keyword_path.stem)

        sensitivity = 0.5
        if len(model_settings) > 1:
            sensitivity = float(model_settings[1])

        sensitivities.append(sensitivity)

    porcupine = pvporcupine.create(
        keyword_paths=[str(keyword_path.absolute()) for keyword_path in keyword_paths],
        sensitivities=sensitivities,
        model_path=str(model_path)
    )

    chunk_format = "h" * porcupine.frame_length
    bytes_per_chunk = porcupine.frame_length * 2  # 16-bit width
    audio_bytes = bytes()
    is_detected = False

    try:
        while True:
            event = read_event()
            if event is None:
                break

            if AudioStop.is_type(event.type):
                break

            if not AudioChunk.is_type(event.type):
                continue

            chunk = AudioChunk.from_event(event)
            audio_bytes += chunk.audio

            while len(audio_bytes) >= bytes_per_chunk:
                unpacked_chunk = struct.unpack_from(
                    chunk_format, audio_bytes[:bytes_per_chunk]
                )
                keyword_index = porcupine.process(unpacked_chunk)
                if keyword_index >= 0:
                    write_event(
                        Detection(
                            name=names[keyword_index], timestamp=chunk.timestamp
                        ).event()
                    )
                    is_detected = True

                audio_bytes = audio_bytes[bytes_per_chunk:]

        if is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
