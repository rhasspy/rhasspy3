import logging
from pathlib import Path
from typing import Iterable, Optional, Union

import pyaudio

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def iter_chunks(
    device: Optional[Union[int, str]],
    rate: int,
    width: int,
    channels: int,
    samples_per_chunk: int,
) -> Iterable[bytes]:
    """Open input stream and yield audio chunks."""
    audio_system = pyaudio.PyAudio()
    try:
        if isinstance(device, str):
            try:
                device = int(device)
            except ValueError:
                for i in range(audio_system.get_device_count()):
                    info = audio_system.get_device_info_by_index(i)
                    if device == info["name"]:
                        device = i
                        break

                assert device is not None, f"No device named: {device}"

        _LOGGER.debug("Device: %s", device)
        stream = audio_system.open(
            input_device_index=device,
            format=audio_system.get_format_from_width(width),
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=samples_per_chunk,
        )

        chunk = stream.read(samples_per_chunk)
        while chunk:
            yield chunk
            chunk = stream.read(samples_per_chunk)
    except KeyboardInterrupt:
        pass
    finally:
        audio_system.terminate()
