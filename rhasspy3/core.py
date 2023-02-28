import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Union

from .config import Config
from .util import merge_dict
from .util.jaml import safe_load

_DIR = Path(__file__).parent
_DEFAULT_CONFIG = _DIR / "configuration.yaml"
_LOGGER = logging.getLogger(__name__)


@dataclass
class Rhasspy:
    config: Config
    config_dir: Path
    base_dir: Path

    @property
    def programs_dir(self) -> Path:
        """Directory where programs are installed."""
        return self.config_dir / "programs"

    @property
    def data_dir(self) -> Path:
        """Directory where models are downloaded."""
        return self.config_dir / "data"

    @staticmethod
    def load(config_dir: Union[str, Path]) -> "Rhasspy":
        """Load and merge configuration.yaml files from rhasspy3 and config dir."""
        config_dir = Path(config_dir)
        config_paths = [
            _DEFAULT_CONFIG,
            config_dir / "configuration.yaml",
        ]
        config_dict: Dict[str, Any] = {}

        for config_path in config_paths:
            if config_path.exists():
                _LOGGER.debug("Loading config from %s", config_path)
                with config_path.open(encoding="utf-8") as config_file:
                    merge_dict(config_dict, safe_load(config_file))
            else:
                _LOGGER.debug("Skipping %s", config_path)

        return Rhasspy(
            config=Config.from_dict(config_dict),
            config_dir=config_dir,
            base_dir=_DIR.parent,
        )
