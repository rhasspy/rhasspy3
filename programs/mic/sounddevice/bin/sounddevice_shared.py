import logging
from pathlib import Path
from typing import Iterable, Optional, Union

import sounddevice

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
    try:
        if isinstance(device, str):
            try:
                device = int(device)
            except ValueError:
                for i, info in enumerate(sounddevice.query_devices()):
                    if device == info["name"]:
                        device = i
                        break

                assert device is not None, f"No device named: {device}"

        _LOGGER.debug("Device: %s", device)

        with sounddevice.RawInputStream(
            samplerate=rate,
            blocksize=samples_per_chunk,
            device=device,
            channels=channels,
            dtype="int16",
        ) as stream:
            chunk, _overflowed = stream.read(samples_per_chunk)
            while chunk:
                yield chunk
                chunk, _overflowed = stream.read(samples_per_chunk)
    except KeyboardInterrupt:
        pass
