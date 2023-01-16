#!/usr/bin/env python3
import argparse
import logging
import struct
import sys
from pathlib import Path
from typing import List

import pvporcupine

_LOGGER = logging.getLogger("porcupine_raw_text")

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
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    # Path to embedded keywords
    keyword_dir = Path(next(iter(pvporcupine.pv_keyword_paths("").values()))).parent

    names: List[str] = []
    keyword_paths: List[Path] = []
    sensitivities: List[float] = []
    for model_settings in args.model:
        keyword_path_str = model_settings[0]
        keyword_path = Path(keyword_path_str)
        if keyword_path.exists():
            keyword_paths.append(keyword_path)
        else:
            keyword_path = keyword_dir / keyword_path_str
            assert keyword_path.exists(), f"Cannot find {keyword_path_str}"

        keyword_paths.append(keyword_path)
        names.append(keyword_path.stem)

        sensitivity = 0.5
        if len(model_settings) > 1:
            sensitivity = float(model_settings[0])

        sensitivities.append(sensitivity)

    porcupine = pvporcupine.create(
        keyword_paths=[str(keyword_path.absolute()) for keyword_path in keyword_paths],
        sensitivities=sensitivities,
    )

    chunk_format = "h" * porcupine.frame_length

    # Read 16Khz, 16-bit mono PCM from stdin
    try:
        chunk = sys.stdin.buffer.read(args.samples_per_chunk)
        while chunk:
            unpacked_chunk = struct.unpack_from(chunk_format, chunk)
            keyword_index = porcupine.process(unpacked_chunk)
            if keyword_index >= 0:
                print(names[keyword_index], flush=True)

            chunk = sys.stdin.buffer.read(args.samples_per_chunk)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
