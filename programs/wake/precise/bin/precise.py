#!/usr/bin/env python3
# Copyright 2021 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import logging
import os
import sys
import typing
from dataclasses import dataclass
from enum import IntEnum
from math import floor
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import tflite_runtime.interpreter as tflite
from sonopy import mfcc_spec


MAX_WAV_VALUE = 32768
_log = logging.getLogger("mycroft_hotword")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to TFLite model")
    parser.add_argument(
        "--sensitivity",
        type=float,
        default=0.8,
        help="Model sensitivity (0-1, default: 0.8)",
    )
    parser.add_argument(
        "--trigger-level",
        type=int,
        default=4,
        help="Number of activations before detection occurs (default: 4)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2048,
        help="Number of bytes to read at a time from stdin",
    )
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    args.model = Path(args.model).absolute()
    engine = TFLiteHotWordEngine(
        local_model_file=args.model,
        sensitivity=args.sensitivity,
        trigger_level=args.trigger_level,
        chunk_size=args.chunk_size,
    )

    if os.isatty(sys.stdin.fileno()):
        print("Reading raw 16-bit 16khz mono audio from stdin", file=sys.stderr)

    is_first_audio = True
    try:
        while True:
            chunk = sys.stdin.buffer.read(args.chunk_size)
            if not chunk:
                break

            if is_first_audio:
                _log.info("Receiving audio")
                is_first_audio = False

            engine.update(chunk)

            if engine.found_wake_word(None):
                print(args.model.name, flush=True)
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


class TFLiteHotWordEngine:
    def __init__(
        self,
        local_model_file: Union[str, Path],
        sensitivity: float = 0.7,
        trigger_level: int = 4,
        chunk_size: int = 2048,
    ):
        self.sensitivity = sensitivity
        self.trigger_level = trigger_level
        self.chunk_size = chunk_size

        self.model_path = Path(local_model_file).absolute()

        self._interpreter: Optional[tflite.Interpreter] = None
        self._params: Optional[ListenerParams] = None
        self._input_details: Optional[Any] = None
        self._output_details: Optional[Any] = None

        # Rolling window of MFCCs (fixed sized)
        self._inputs: Optional[np.ndarray] = None

        # Current MFCC timestep
        self._inputs_idx: int = 0

        # Bytes for one window of audio
        self._window_bytes: int = 0

        # Bytes for one MFCC hop
        self._hop_bytes: int = 0

        # Raw audio
        self._chunk_buffer = bytes()

        # Activation level (> trigger_level = wake word found)
        self._activation: int = 0

        # True if wake word was found during last update
        self._is_found = False

        # There doesn't seem to be an initialize() method for wake word plugins,
        # so we'll load the model here.
        self._load_model()

        # Last probability
        self._probability: Optional[float] = None

    def _load_model(self):
        _log.debug("Loading model from %s", self.model_path)
        self._interpreter = tflite.Interpreter(model_path=str(self.model_path))
        self._interpreter.allocate_tensors()
        self._input_details = self._interpreter.get_input_details()
        self._output_details = self._interpreter.get_output_details()

        # TODO: Load these from adjacent file
        self._params = ListenerParams()

        self._window_bytes = self._params.window_samples * self._params.sample_depth
        self._hop_bytes = self._params.hop_samples * self._params.sample_depth

        # Rolling window of MFCCs (fixed sized)
        self._inputs = np.zeros(
            (1, self._params.n_features, self._params.n_mfcc), dtype=np.float32
        )

    def update(self, chunk):
        self._is_found = False
        self._chunk_buffer += chunk
        self._probability = None

        # Process all available windows
        while len(self._chunk_buffer) >= self._window_bytes:
            # Process current audio
            audio = buffer_to_audio(self._chunk_buffer)

            # TODO: Implement different MFCC algorithms
            mfccs = mfcc_spec(
                audio,
                self._params.sample_rate,
                (self._params.window_samples, self._params.hop_samples),
                num_filt=self._params.n_filt,
                fft_size=self._params.n_fft,
                num_coeffs=self._params.n_mfcc,
            )

            num_timesteps = mfccs.shape[0]

            # Remove processed audio from buffer
            self._chunk_buffer = self._chunk_buffer[num_timesteps * self._hop_bytes :]

            # Check if we have a full set of inputs yet
            inputs_end_idx = self._inputs_idx + num_timesteps
            if inputs_end_idx > self._inputs.shape[1]:
                # Full set, need to roll back existing inputs
                self._inputs = np.roll(self._inputs, -num_timesteps, axis=1)
                inputs_end_idx = self._inputs.shape[1]
                self._inputs_idx = inputs_end_idx - num_timesteps

            # Insert new MFCCs at the end
            self._inputs[0, self._inputs_idx : inputs_end_idx, :] = mfccs
            self._inputs_idx += num_timesteps
            if inputs_end_idx < self._inputs.shape[1]:
                # Don't have a full set of inputs yet
                continue

            # TODO: Add deltas

            # raw_output
            self._interpreter.set_tensor(self._input_details[0]["index"], self._inputs)
            self._interpreter.invoke()
            raw_output = self._interpreter.get_tensor(self._output_details[0]["index"])
            prob = raw_output[0][0]

            if (prob < 0.0) or (prob > 1.0):
                # TODO: Handle out of range.
                # Not seeing these currently, so ignoring.
                continue

            self._probability = prob.item()

            # Decode
            activated = prob > 1.0 - self.sensitivity
            triggered = False
            if activated or (self._activation < 0):
                # Increase activation
                self._activation += 1

                triggered = self._activation > self.trigger_level
                if triggered or (activated and (self._activation < 0)):
                    # Push activation down far to avoid an accidental re-activation
                    self._activation = -(8 * 2048) // self.chunk_size
            elif self._activation > 0:
                # Decrease activation
                self._activation -= 1

            if triggered:
                self._is_found = True
                _log.debug("Triggered")
                break

        return self._is_found

    def found_wake_word(self, frame_data):
        return self._is_found

    def reset(self):
        self._inputs = np.zeros(
            (1, self._params.n_features, self._params.n_mfcc), dtype=np.float32
        )
        self._activation = 0
        self._is_found = False
        self._inputs_idx = 0
        self._chunk_buffer = bytes()

    @property
    def probability(self) -> Optional[float]:
        return self._probability


# -----------------------------------------------------------------------------


class Vectorizer(IntEnum):
    """
    Chooses which function to call to vectorize audio

    Options:
        mels: Convert to a compressed Mel spectrogram
        mfccs: Convert to a MFCC spectrogram
        speechpy_mfccs: Legacy option to convert to MFCCs using old library
    """

    mels = 1
    mfccs = 2
    speechpy_mfccs = 3


@dataclass
class ListenerParams:
    """
    General pipeline information:
     - Audio goes through a series of transformations to convert raw audio into machine readable data
     - These transformations are as follows:
       - Raw audio -> chopped audio
         - buffer_t, sample_depth: Input audio loaded and truncated using these value
         - window_t, hop_t: Linear audio chopped into overlapping frames using a sliding window
       - Chopped audio -> FFT spectrogram
         - n_fft, sample_rate: Each audio frame is converted to n_fft frequency intensities
       - FFT spectrogram -> Mel spectrogram (compressed)
         - n_filt: Each fft frame is compressed to n_filt summarized mel frequency bins/bands
       - Mel spectrogram -> MFCC
         - n_mfcc: Each mel frame is converted to MFCCs and the first n_mfcc values are taken
       - Disabled by default: Last phase -> Delta vectors
         - use_delta: If this value is true, the difference between consecutive vectors is concatenated to each frame

    Parameters for audio pipeline:
     - buffer_t: Input size of audio. Wakeword must fit within this time
     - window_t: Time of the window used to calculate a single spectrogram frame
     - hop_t: Time the window advances forward to calculate the next spectrogram frame
     - sample_rate: Input audio sample rate
     - sample_depth: Bytes per input audio sample
     - n_fft: Size of FFT to generate from audio frame
     - n_filt: Number of filters to compress FFT to
     - n_mfcc: Number of MFCC coefficients to use
     - use_delta: If True, generates "delta vectors" before sending to network
     - vectorizer: The type of input fed into the network. Options listed in class Vectorizer
     - threshold_config: Output distribution configuration automatically generated from precise-calc-threshold
     - threshold_center: Output distribution center automatically generated from precise-calc-threshold
    """

    buffer_t: float = 1.5
    window_t: float = 0.1
    hop_t: float = 0.05
    sample_rate: int = 16000
    sample_depth: int = 2
    n_fft: int = 512
    n_filt: int = 20
    n_mfcc: int = 13
    use_delta: bool = False
    vectorizer: int = Vectorizer.mfccs
    threshold_config: typing.Tuple[typing.Tuple[int, ...], ...] = ((6, 4),)
    threshold_center: float = 0.2

    @property
    def buffer_samples(self):
        """buffer_t converted to samples, truncating partial frames"""
        samples = int(self.sample_rate * self.buffer_t + 0.5)
        return self.hop_samples * (samples // self.hop_samples)

    @property
    def n_features(self):
        """Number of timesteps in one input to the network"""
        return 1 + int(
            floor((self.buffer_samples - self.window_samples) / self.hop_samples)
        )

    @property
    def window_samples(self):
        """window_t converted to samples"""
        return int(self.sample_rate * self.window_t + 0.5)

    @property
    def hop_samples(self):
        """hop_t converted to samples"""
        return int(self.sample_rate * self.hop_t + 0.5)

    @property
    def max_samples(self):
        """The input size converted to audio samples"""
        return int(self.buffer_t * self.sample_rate)

    @property
    def feature_size(self):
        """The size of an input vector generated with these parameters"""
        num_features = {
            Vectorizer.mfccs: self.n_mfcc,
            Vectorizer.mels: self.n_filt,
            Vectorizer.speechpy_mfccs: self.n_mfcc,
        }[self.vectorizer]
        if self.use_delta:
            num_features *= 2
        return num_features


def chunk_audio(
    audio: np.ndarray, chunk_size: int
) -> typing.Generator[np.ndarray, None, None]:
    for i in range(chunk_size, len(audio), chunk_size):
        yield audio[i - chunk_size : i]


def buffer_to_audio(audio_buffer: bytes) -> np.ndarray:
    """Convert a raw mono audio byte string to numpy array of floats"""
    return np.frombuffer(audio_buffer, dtype="<i2").astype(
        np.float32, order="C"
    ) / float(MAX_WAV_VALUE)


def audio_to_buffer(audio: np.ndarray) -> bytes:
    """Convert a numpy array of floats to raw mono audio"""
    return (audio * MAX_WAV_VALUE).astype("<i2").tobytes()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
