#!/usr/bin/env python3

import sounddevice


def main() -> None:
    for info in sounddevice.query_devices():
        print(info)


if __name__ == "__main__":
    main()
