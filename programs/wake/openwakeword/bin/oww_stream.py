#!/usr/bin/env python3
import logging
from collections import Counter
from pathlib import Path

import numpy as np
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

    oww_model = load_openwakeword(args)
    bytes_per_chunk = args.samples_per_chunk * 2  # 16-bit samples

    audio_bytes = bytes()
    is_detected = False

    activations: "Counter[str]" = Counter()
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
                oww_model.predict(
                    np.frombuffer(audio_bytes[:bytes_per_chunk], dtype=np.int16)
                )
                for model_key, model_score in oww_model.prediction_buffer.items():
                    if model_score[-1] >= args.threshold:
                        # Activated
                        activations[model_key] += 1
                    else:
                        # Decay back to 0
                        activations[model_key] = max(0, activations[model_key])

                    if activations[model_key] >= args.trigger_level:
                        # Report and enter refractory period
                        write_event(
                            Detection(name=model_key, timestamp=chunk.timestamp).event()
                        )
                        is_detected = True
                        activations[model_key] = -args.refractory_level

                audio_bytes = audio_bytes[bytes_per_chunk:]

        if is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
