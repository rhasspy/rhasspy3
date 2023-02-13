#!/usr/bin/env python3

import pyaudio


def main() -> None:
    audio_system = pyaudio.PyAudio()
    for i in range(audio_system.get_device_count()):
        print(audio_system.get_device_info_by_index(i))


if __name__ == "__main__":
    main()
