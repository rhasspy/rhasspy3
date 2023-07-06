#!/usr/bin/env python3
import logging
from pathlib import Path

from oww_shared import get_arg_parser, load_openwakeword

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

    oww_state = load_openwakeword(args)
    is_detected = True

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
            for ww_name, ww_probability in oww_state.predict(chunk.audio).items():
                write_event(Detection(name=ww_name, timestamp=chunk.timestamp).event())
                is_detected = True
                _LOGGER.debug("Triggered %s, probability=%s", ww_name, ww_probability)

        if not is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
