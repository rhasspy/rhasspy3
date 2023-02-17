import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Union

from .config import Config
from .util import merge_dict
from .util.jaml import safe_load

_DIR = Path(__file__).parent
_LOGGER = logging.getLogger(__name__)


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
        config_paths = [
            config_dir / "configuration.default.yaml",
            config_dir / "configuration.yaml",
        ]
        config_dict: Dict[str, Any] = {}

        for config_path in config_paths:
            _LOGGER.debug("Loading config from %s", config_path)
            with config_path.open(encoding="utf-8") as config_file:
                merge_dict(config_dict, safe_load(config_file))

        return Rhasspy(
            config=Config.from_dict(config_dict),
            config_dir=config_dir,
            base_dir=_DIR.parent,
        )
