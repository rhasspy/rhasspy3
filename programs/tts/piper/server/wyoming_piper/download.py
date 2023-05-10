"""Utility for downloading Piper voices."""
import logging
import tarfile
from pathlib import Path
from typing import Dict, Optional, Union
from urllib.request import urlopen

from .file_hash import get_file_hash
from .voice_hashes import VOICE_HASHES

URL_FORMAT = "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{voice_name}.tar.gz"

_LOGGER = logging.getLogger(__name__)


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

    expected_hash = VOICE_HASHES.get(voice_name)
    if expected_hash is None:
        # No expected hash, fall back to checking for a non-empty ONNX model
        if voice_onnx.exists() and (voice_onnx.stat().st_size > 0):
            return voice_onnx

        return None

    actual_hash: Dict[str, str] = {}
    for hash_key in expected_hash:
        file_to_hash = dest_dir / hash_key
        if file_to_hash.exists():
            actual_hash[hash_key] = get_file_hash(file_to_hash)
        else:
            # File is missing
            actual_hash[hash_key] = ""

    if actual_hash == expected_hash:
        # Hashes match
        return voice_onnx

    # Hashes do not match
    _LOGGER.warning("Voice hashes do not match")
    _LOGGER.warning("Expected: %s", expected_hash)
    _LOGGER.warning("Got: %s", actual_hash)

    return None


def get_voice_hash(model_dir: Union[str, Path]) -> Dict[str, str]:
    """Get hashes for relevant voice files."""
    model_dir = Path(model_dir)
    files_to_hash = [
        model_dir / "model.bin",
        model_dir / "config.json",
        model_dir / "vocabulary.txt",
    ]

    model_hash: Dict[str, str] = {}
    for file_to_hash in files_to_hash:
        hash_key = str(file_to_hash.relative_to(model_dir))
        if file_to_hash.exists():
            model_hash[hash_key] = get_file_hash(file_to_hash)
        else:
            # File is missing
            model_hash[hash_key] = ""

    return model_hash
