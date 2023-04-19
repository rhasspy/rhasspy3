"""Utility for downloading faster-whisper models."""
import shutil
import tarfile
from enum import Enum
from pathlib import Path
from typing import Optional, Union
from urllib.request import urlopen

URL_FORMAT = "https://github.com/rhasspy/models/releases/download/v1.0/asr_faster-whisper-{model}.tar.gz"


class FasterWhisperModel(str, Enum):
    """Available faster-whisper models."""

    TINY = "tiny"
    TINY_INT8 = "tiny-int8"
    BASE = "base"
    BASE_INT8 = "base-int8"
    SMALL = "small"
    SMALL_INT8 = "small-int8"
    MEDIUM = "medium"
    MEDIUM_INT8 = "medium-int8"


def download_model(model: FasterWhisperModel, dest_dir: Union[str, Path]) -> Path:
    """
    Downloads/extracts tar.gz model directly to destination directory.

    Returns directory of downloaded model.
    """
    dest_dir = Path(dest_dir)
    model_dir = dest_dir / model.value

    if model_dir.is_dir():
        # Remove model directory if it already exists
        shutil.rmtree(model_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)

    model_url = URL_FORMAT.format(model=model)
    with urlopen(model_url) as response:
        with tarfile.open(mode="r|*", fileobj=response) as tar_gz:
            tar_gz.extractall(dest_dir)

    return model_dir


def find_model(model: FasterWhisperModel, dest_dir: Union[str, Path]) -> Optional[Path]:
    """Returns model directory if model exists."""
    dest_dir = Path(dest_dir)
    model_dir = dest_dir / model.value
    model_bin = model_dir / "model.bin"

    if model_bin.exists() and (model_bin.stat().st_size > 0):
        return model_dir

    return None
