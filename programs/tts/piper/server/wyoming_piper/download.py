"""Utility for downloading Piper voices."""
import tarfile
from pathlib import Path
from typing import Optional, Union
from urllib.request import urlopen

URL_FORMAT = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{voice_name}.tar.gz"


def download_voice(voice_name: str, dest_dir: Union[str, Path]) -> Path:
    """
    Downloads/extracts tar.gz voice directly to destination directory.

    Returns path to ONNX model file.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    voice_url = URL_FORMAT.format(voice_name=voice_name)
    with urlopen(voice_url) as response:
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            tar_gz.extractall(dest_dir)

    return dest_dir / f"{voice_name}.onnx"


def find_voice(voice_name: str, dest_dir: Union[str, Path]) -> Optional[Path]:
    """Returns path to voice ONNX file if it exists."""
    dest_dir = Path(dest_dir)
    voice_onnx = dest_dir / f"{voice_name}.onnx"

    if voice_onnx.exists() and (voice_onnx.stat().st_size > 0):
        return voice_onnx

    return None
