import argparse
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Final

import numpy as np
import tflite_runtime.interpreter as tflite

_MAX_SECONDS: Final = 10
_BATCH_SIZE: Final = 1

_SAMPLE_RATE: Final = 16000  # 16Khz
_SAMPLE_WIDTH: Final = 2  # 16-bit samples
_MAX_SAMPLES: Final = _MAX_SECONDS * _SAMPLE_RATE

SAMPLES_PER_CHUNK: Final = 1280  # 80 ms @ 16Khz
_BYTES_PER_CHUNK: Final = SAMPLES_PER_CHUNK * _SAMPLE_WIDTH

# window = 400, hop length = 160
_MELS_PER_SECOND: Final = 97
_MAX_MELS: Final = _MAX_SECONDS * _MELS_PER_SECOND
MEL_SAMPLES: Final = 1760
NUM_MELS: Final = 32

EMB_FEATURES: Final = 76  # 775 ms
EMB_STEP: Final = 8
_MAX_EMB: Final = _MAX_SECONDS * EMB_STEP
WW_FEATURES: Final = 96

_DIR = Path(__file__).parent
_PROGRAM_DIR = _DIR.parent
_SHARE_DIR = _PROGRAM_DIR / "share"

_LOGGER = logging.getLogger()


@dataclass
class WakeWordState:
    ww_input_index: int
    ww_output_index: int
    ww_windows: int
    new_embeddings: int = 0
    embeddings: np.ndarray = field(
        default_factory=lambda: np.zeros(
            shape=(_MAX_EMB, WW_FEATURES), dtype=np.float32
        )
    )
    activations: int = 0
    threshold: float = 0.5
    trigger_level: int = 4
    refractory_activations: int = 30


@dataclass
class OpenWakeWordState:
    melspec_model: tflite.Interpreter
    embedding_model: tflite.Interpreter
    ww_models: Dict[str, tflite.Interpreter]

    _audio: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_SAMPLES,), dtype=np.float32)
    )
    _new_audio_samples: int = 0

    _mels: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_MELS, NUM_MELS), dtype=np.float32)
    )
    _new_mels: int = 0
    _melspec_input_index: int = -1
    _melspec_output_index: int = -1

    _embedding_input_index: int = -1
    _embedding_output_index: int = -1

    _ww_state: Dict[str, WakeWordState] = field(default_factory=dict)

    def __post_init__(self):
        self._melspec_input_index = self.melspec_model.get_input_details()[0]["index"]
        self._melspec_output_index = self.melspec_model.get_output_details()[0]["index"]

        self.melspec_model.resize_tensor_input(
            self._melspec_input_index,
            (_BATCH_SIZE, MEL_SAMPLES),
            strict=True,
        )
        self.melspec_model.allocate_tensors()

        self._embedding_input_index = self.embedding_model.get_input_details()[0][
            "index"
        ]
        self._embedding_output_index = self.embedding_model.get_output_details()[0][
            "index"
        ]

        self.embedding_model.resize_tensor_input(
            self._embedding_input_index,
            (_BATCH_SIZE, EMB_FEATURES, NUM_MELS, 1),
            strict=True,
        )
        self.embedding_model.allocate_tensors()

        for ww_name, ww_model in self.ww_models.items():
            ww_input = ww_model.get_input_details()[0]
            ww_input_index = ww_input["index"]
            ww_windows = ww_input["shape"][1]

            ww_model.resize_tensor_input(
                ww_input_index,
                (_BATCH_SIZE, ww_windows, WW_FEATURES),
                strict=False,  # must be False for non-dynamic batch dim
            )
            ww_model.allocate_tensors()

            self._ww_state[ww_name] = WakeWordState(
                ww_input_index=ww_input_index,
                ww_output_index=ww_model.get_output_details()[0]["index"],
                ww_windows=ww_windows,
            )

    def predict(self, chunk_bytes: bytes) -> Dict[str, float]:
        """Get wake word predictions for audio."""

        # NOTE: Audio is *not* normalized
        chunk_array = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)

        # Shift samples left
        self._audio[: -len(chunk_array)] = self._audio[len(chunk_array) :]

        # Add new samples to end
        self._audio[-len(chunk_array) :] = chunk_array
        self._new_audio_samples = min(
            len(self._audio),
            self._new_audio_samples + len(chunk_array),
        )

        detections: Dict[str, float] = {}
        while self._new_audio_samples >= MEL_SAMPLES:
            self._process_audio(detections)
            self._new_audio_samples = max(
                0, self._new_audio_samples - SAMPLES_PER_CHUNK
            )

        return detections

    def _process_audio(self, detections: Dict[str, float]) -> None:
        """Convert raw audio to mels."""

        # Generate mels
        # melspec = [batch x samples (min: 1280)] => [batch x 1 x window x mels (32)]
        # stft window size: 25ms (400)
        # stft window step: 10ms (160)
        # mel band limits: 60Hz - 3800Hz
        # mel frequency bins: 32
        self.melspec_model.set_tensor(
            self._melspec_input_index,
            self._audio[  # new audio samples
                np.newaxis,  # batch
                -self._new_audio_samples : len(self._audio)
                - self._new_audio_samples
                + MEL_SAMPLES,
            ],
        )
        self.melspec_model.invoke()
        mels = self.melspec_model.get_tensor(self._melspec_output_index)
        mels = (mels / 10) + 2  # transform to fit embedding

        # Shift
        num_mel_windows = mels.shape[2]
        self._mels[:-num_mel_windows] = self._mels[num_mel_windows:]

        # Overwrite
        self._mels[-num_mel_windows:] = mels[0, 0, :, :]
        self._new_mels = min(len(self._mels), self._new_mels + num_mel_windows)

        while self._new_mels >= EMB_FEATURES:
            self._process_mels(detections)

            # Shift forward by 80ms
            self._new_mels = max(0, self._new_mels - EMB_STEP)

    def _process_mels(self, detections: Dict[str, float]) -> None:
        """Convert mels to embeddings."""
        # Generate embeddings
        # embedding = [batch x window x mels (32) x 1] => [batch x 1 x 1 x features (96)]
        self.embedding_model.set_tensor(
            self._embedding_input_index,
            self._mels[
                np.newaxis,  # batch
                -self._new_mels : len(self._mels) - self._new_mels + EMB_FEATURES,
                :,
                np.newaxis,
            ],
        )
        self.embedding_model.invoke()

        embeddings = self.embedding_model.get_tensor(self._embedding_output_index)
        num_embedding_windows = embeddings.shape[2]  # 1

        for ww_name, ww_state in self._ww_state.items():
            # Shift
            ww_state.embeddings[:-num_embedding_windows] = ww_state.embeddings[
                num_embedding_windows:
            ]

            # Overwrite
            ww_state.embeddings[-num_embedding_windows:] = embeddings[0, 0, 0, :]
            ww_state.new_embeddings = min(
                len(ww_state.embeddings),
                ww_state.new_embeddings + num_embedding_windows,
            )

            while ww_state.new_embeddings >= ww_state.ww_windows:
                self._process_embeddings(ww_name, detections)

                # Shift forward by one embedding
                ww_state.new_embeddings = max(0, ww_state.new_embeddings - 1)

    def _process_embeddings(self, ww_name: str, detections: Dict[str, float]) -> None:
        """Convert embeddings to wake word model probabilities."""
        ww_state = self._ww_state[ww_name]
        ww_model = self.ww_models[ww_name]

        # Generate probabilities
        # ww = [batch x window x features (96)] => [batch x probability]
        ww_model.set_tensor(
            ww_state.ww_input_index,
            ww_state.embeddings[
                np.newaxis,  # batch
                -ww_state.new_embeddings : len(ww_state.embeddings)
                - ww_state.new_embeddings
                + ww_state.ww_windows,
                :,
            ],
        )
        ww_model.invoke()
        probabilities = ww_model.get_tensor(ww_state.ww_output_index)
        for probability in probabilities:
            if probability.item() >= ww_state.threshold:
                # Increase activation
                ww_state.activations += 1

                if ww_state.activations >= ww_state.trigger_level:
                    # Wake word triggered, enter refractory period
                    detections[ww_name] = probability.item()
                    ww_state.activations = -ww_state.refractory_activations
            else:
                # Back towards 0
                ww_state.activations = max(0, ww_state.activations - 1)


def get_arg_parser() -> argparse.ArgumentParser:
    """Get shared command-line argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--trigger-level", type=int, default=4)
    parser.add_argument("--refractory-level", type=int, default=30)
    parser.add_argument("--samples-per-chunk", type=int, default=1280)
    #
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        help="Path to openWakeWord model (.tflite)",
    )
    parser.add_argument(
        "--melspec_model",
        default=_SHARE_DIR / "melspectrogram.tflite",
        help="Path to melspectrogram model (.tflite)",
    )
    parser.add_argument(
        "--embedding_model",
        default=_SHARE_DIR / "embedding_model.tflite",
        help="Path to embedding model (.tflite)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Number of threads in tflite interpreters",
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    return parser


def load_openwakeword(args: argparse.Namespace) -> OpenWakeWordState:
    """Loads openWakeWord with the supplied options."""
    return OpenWakeWordState(
        melspec_model=tflite.Interpreter(
            model_path=str(args.melspec_model), num_threads=args.threads
        ),
        embedding_model=tflite.Interpreter(
            model_path=str(args.embedding_model), num_threads=args.threads
        ),
        ww_models={
            ww_model_path: tflite.Interpreter(
                model_path=str(ww_model_path), num_threads=args.threads
            )
            for ww_model_path in args.model
        },
    )
