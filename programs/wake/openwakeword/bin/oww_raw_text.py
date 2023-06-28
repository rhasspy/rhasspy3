#!/usr/bin/env python3
import logging
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from oww_shared import get_arg_parser, load_openwakeword

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

    # Read 16Khz, 16-bit mono PCM from stdin
    activations: "Counter[str]" = Counter()
    try:
        chunk = bytes()
        next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while next_chunk:
            while len(chunk) >= bytes_per_chunk:
                oww_model.predict(
                    np.frombuffer(chunk[:bytes_per_chunk], dtype=np.int16)
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
                        print(model_key, flush=True)
                        activations[model_key] = -args.refractory_level

                chunk = chunk[bytes_per_chunk:]

            next_chunk = sys.stdin.buffer.read(bytes_per_chunk)
            chunk += next_chunk
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
