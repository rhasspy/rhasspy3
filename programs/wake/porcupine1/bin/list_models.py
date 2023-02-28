#!/usr/bin/env python3
from pathlib import Path

import pvporcupine


def main() -> None:
    """Main method."""

    for keyword_path in sorted(pvporcupine.pv_keyword_paths("").values()):
        model_name = Path(keyword_path).name
        print(model_name)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
