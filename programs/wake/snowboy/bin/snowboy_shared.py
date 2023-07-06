#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path
from typing import Dict

from snowboy import snowboydecoder, snowboydetect


def get_arg_parser() -> argparse.ArgumentParser:
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
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    return parser


def load_snowboy(args: argparse.Namespace) -> Dict[str, snowboydetect.SnowboyDetect]:
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

    return detectors
