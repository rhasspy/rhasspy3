#!/usr/bin/env python3
from pathlib import Path

_DIR = Path(__file__).parent
_PROGRAM_DIR = _DIR.parent
_SHARE_DIR = _PROGRAM_DIR / "share"


def main() -> None:
    """Main method."""

    for tflite_model in _SHARE_DIR.glob("*.tflite"):
        if tflite_model.stem in ("melspectrogram", "embedding_model"):
            continue

        print(tflite_model)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
