#!/usr/bin/env python3
import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
import onnxruntime

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Silero model")
    parser.add_argument("--samples-per-chunk", type=int, default=512)
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * 2  # 16-bit
    detector = SileroDetector(args.model)
    detector.start()

    try:
        chunk = sys.stdin.buffer.read(bytes_per_chunk)
        while chunk:
            speech_probability = detector.get_speech_probability(chunk)
            print(speech_probability, flush=True)
            chunk = sys.stdin.buffer.read(bytes_per_chunk)
    except (KeyboardInterrupt, BrokenPipeError):
        pass


# -----------------------------------------------------------------------------


@dataclass
class SileroDetector:
    model: Union[str, Path]
    _session: Optional[onnxruntime.InferenceSession] = None
    _h_array: Optional[np.ndarray] = None
    _c_array: Optional[np.ndarray] = None

    def start(self):
        _LOGGER.debug("Loading VAD model: %s", self.model)
        self._session = onnxruntime.InferenceSession(str(self.model))
        self._session.intra_op_num_threads = 1
        self._session.inter_op_num_threads = 1

        self._h_array = np.zeros((2, 1, 64)).astype("float32")
        self._c_array = np.zeros((2, 1, 64)).astype("float32")

    def get_speech_probability(self, chunk: bytes) -> float:
        assert self._session is not None
        audio_array = np.frombuffer(chunk, dtype=np.int16)

        # Add batch dimension
        audio_array = np.expand_dims(audio_array, 0)

        ort_inputs = {
            "input": audio_array.astype(np.float32),
            "h0": self._h_array,
            "c0": self._c_array,
        }
        ort_outs = self._session.run(None, ort_inputs)
        out, self._h_array, self._c_array = ort_outs
        probability = out.squeeze(2)[:, 1].item()
        return probability

    def stop(self):
        self._session = None
        self._h_array = None
        self._c_array = None

    def reset(self):
        self._h_array.fill(0)
        self._c_array.fill(0)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
