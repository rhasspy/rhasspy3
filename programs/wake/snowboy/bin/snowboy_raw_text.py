#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

from snowboy import snowboydecoder, snowboydetect

_LOGGER = logging.getLogger("snowboy_raw_text")

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        nargs="+",
        help="Snowboy model settings (path, [sensitivity], [audio_gain], [apply_frontend])",
    )
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    # logging.basicConfig wouldn't work if a handler already existed.
    # snowboy must mess with logging, so this resets it.
    logging.getLogger().handlers = []
    logging.basicConfig(level=logging.INFO)

    # Load model settings
    detectors: Dict[str, snowboydetect.SnowboyDetect] = {}

    for model_settings in args.model:
        model_path = Path(model_settings[0])

        sensitivity = "0.5"
        if len(model_settings) > 1:
            sensitivity = model_settings[1]

        audio_gain = 1.0
        if len(model_settings) > 2:
            audio_gain = float(model_settings[2])

        apply_frontend = False
        if len(model_settings) > 3:
            apply_frontend = model_settings[3].strip().lower() == "true"

        detector = snowboydetect.SnowboyDetect(
            snowboydecoder.RESOURCE_FILE.encode(), str(model_path).encode()
        )

        detector.SetSensitivity(sensitivity.encode())
        detector.SetAudioGain(audio_gain)
        detector.ApplyFrontend(apply_frontend)

        detectors[model_path.stem] = detector

    # Read 16Khz, 16-bit mono PCM from stdin
    try:
        chunk = sys.stdin.buffer.read(args.samples_per_chunk)
        while chunk:
            for name, detector in detectors.items():
                # Return is:
                # -2 silence
                # -1 error
                #  0 voice
                #  n index n-1
                result_index = detector.RunDetection(chunk)

                if result_index > 0:
                    # Detection
                    print(name, flush=True)

            chunk = sys.stdin.buffer.read(args.samples_per_chunk)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
