from dataclasses import dataclass, field
from typing import Dict, Final, Tuple

import numpy as np

from wyoming.server import AsyncEventHandler

_AUTOFILL_SECONDS: Final = 3
_MAX_SECONDS: Final = 10

_SAMPLE_RATE: Final = 16000  # 16Khz
_SAMPLE_WIDTH: Final = 2  # 16-bit samples
_MAX_SAMPLES: Final = _MAX_SECONDS * _SAMPLE_RATE

SAMPLES_PER_CHUNK: Final = 1280  # 80 ms @ 16Khz
_BYTES_PER_CHUNK: Final = SAMPLES_PER_CHUNK * _SAMPLE_WIDTH
MS_PER_CHUNK: Final = SAMPLES_PER_CHUNK // _SAMPLE_RATE

# window = 400, hop length = 160
_MELS_PER_SECOND: Final = 97
_MAX_MELS: Final = _MAX_SECONDS * _MELS_PER_SECOND
MEL_SAMPLES: Final = 1760
NUM_MELS: Final = 32

EMB_FEATURES: Final = 76  # 775 ms
EMB_STEP: Final = 8
_MAX_EMB: Final = _MAX_SECONDS * EMB_STEP
WW_FEATURES: Final = 96

CLIENT_ID_TYPE = Tuple[str, int]


@dataclass
class WakeWordData:
    new_embeddings: int = 0
    embeddings: np.ndarray = field(
        default_factory=lambda: np.zeros(
            shape=(_MAX_EMB, WW_FEATURES), dtype=np.float32
        )
    )
    embeddings_timestamp: int = 0
    is_detected: bool = False
    activations: int = 0
    threshold: float = 0.5
    trigger_level: int = 4

    def reset(self) -> None:
        self.new_embeddings = 0
        self.embeddings.fill(0)
        self.is_detected = False
        self.activations = 0


@dataclass
class ClientData:
    event_handler: AsyncEventHandler
    new_audio_samples: int = _AUTOFILL_SECONDS * _SAMPLE_RATE
    audio_timestamp: int = 0
    audio: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_SAMPLES,), dtype=np.float32)
    )
    new_mels: int = 0
    mels_timestamp: int = 0
    mels: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_MELS, NUM_MELS), dtype=np.float32)
    )
    wake_words: Dict[str, WakeWordData] = field(default_factory=dict)

    def reset(self) -> None:
        self.audio.fill(0)
        self.new_audio_samples = 0
        self.mels.fill(0)
        self.new_mels = 0
        for ww_data in self.wake_words.values():
            ww_data.reset()
