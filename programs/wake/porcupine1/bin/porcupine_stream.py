#!/usr/bin/env python3
import logging
import struct
from pathlib import Path

from porcupine_shared import get_arg_parser, load_porcupine

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.wake import Detection, NotDetected

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = get_arg_parser()
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    porcupine, names = load_porcupine(args)

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
