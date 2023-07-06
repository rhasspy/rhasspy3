#!/usr/bin/env python3
import logging
from pathlib import Path

from precise_shared import get_arg_parser, load_precise

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

    engine = load_precise(args)
    bytes_per_chunk = args.samples_per_chunk * 2  # 16-bit samples

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
                engine.update(audio_bytes[:bytes_per_chunk])
                if engine.found_wake_word(None):
                    write_event(
                        Detection(name=args.model, timestamp=chunk.timestamp).event()
                    )
                    is_detected = True
                    _LOGGER.debug("Triggered %s", args.model)

                audio_bytes = audio_bytes[bytes_per_chunk:]

        if is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
