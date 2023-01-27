from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Union

from yaml import safe_load

from .config import Config

_DIR = Path(__file__).parent


class Domain(str, Enum):
    SPEECH_TO_TEXT = "asr"


@dataclass
class Rhasspy:
    config: Config
    config_dir: Path
    base_dir: Path

    @staticmethod
    def load(config_dir: Union[str, Path]) -> "Rhasspy":
        config_dir = Path(config_dir)
        config_path = config_dir / "configuration.yaml"
        with config_path.open(encoding="utf-8") as config_file:
            config_dict = safe_load(config_file)

        return Rhasspy(
            config=Config.from_dict(config_dict),
            config_dir=config_dir,
            base_dir=_DIR.parent,
        )
