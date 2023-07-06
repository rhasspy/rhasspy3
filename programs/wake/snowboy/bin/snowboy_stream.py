#!/usr/bin/env python3
import logging
from pathlib import Path

from snowboy_shared import get_arg_parser, load_snowboy

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

    # logging.basicConfig wouldn't work if a handler already existed.
    # snowboy must mess with logging, so this resets it.
    logging.getLogger().handlers = []
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    detectors = load_snowboy(args)
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
                for name, detector in detectors.items():
                    # Return is:
                    # -2 silence
                    # -1 error
                    #  0 voice
                    #  n index n-1
                    result_index = detector.RunDetection(audio_bytes[:bytes_per_chunk])

                    if result_index > 0:
                        # Detection
                        write_event(
                            Detection(name=name, timestamp=chunk.timestamp).event()
                        )
                        is_detected = True
                        _LOGGER.debug("Triggered %s", name)

                audio_bytes = audio_bytes[bytes_per_chunk:]

        if is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
