#!/usr/bin/env python3
from openwakeword import models


def main() -> None:
    """Main method."""

    for model_name in sorted(models):
        print(model_name)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
