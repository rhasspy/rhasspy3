#!/usr/bin/env python3
import argparse
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import numpy as np
import onnxruntime

from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    AudioChunk,
    AudioStart,
    AudioStop,
)
from rhasspy3.event import read_event, write_event
from rhasspy3.vad import VoiceStarted, VoiceStopped

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Silero model")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Speech probability threshold (0-1)",
    )
    parser.add_argument(
        "--speech-seconds",
        type=float,
        default=0.3,
    )
    parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.5,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--reset-seconds",
        type=float,
        default=1,
    )
    parser.add_argument("--samples-per-chunk", type=int, default=512)
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    detector = SileroDetector(args.model, args.threshold)
    detector.start()

    segmenter = Segmenter(
        speech_seconds=args.speech_seconds,
        silence_seconds=args.silence_seconds,
        timeout_seconds=args.timeout_seconds,
        reset_seconds=args.reset_seconds,
    )
    is_first_audio = True
    sent_started = False
    sent_stopped = False
    last_stop_timestamp: Optional[int] = None
    audio_bytes = bytes()
    bytes_per_chunk = args.samples_per_chunk * DEFAULT_IN_WIDTH * DEFAULT_IN_CHANNELS
    seconds_per_chunk = args.samples_per_chunk / DEFAULT_IN_RATE

    try:
        while True:
            event = read_event(sys.stdin.buffer)
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                if sent_started and sent_stopped:
                    # Wait for audio to start again
                    continue

                if is_first_audio:
                    _LOGGER.debug("Receiving audio")
                    is_first_audio = False

                chunk = AudioChunk.from_event(event)
                audio_bytes += chunk.audio

                # Handle uneven chunk sizes
                while len(audio_bytes) >= bytes_per_chunk:
                    detector_audio_bytes = audio_bytes[:bytes_per_chunk]
                    is_speech = detector.is_speech(detector_audio_bytes)
                    timestamp = (
                        time.monotonic_ns()
                        if chunk.timestamp is None
                        else chunk.timestamp
                    )
                    last_stop_timestamp = timestamp + chunk.milliseconds
                    segmenter.process(
                        chunk=detector_audio_bytes,
                        chunk_seconds=seconds_per_chunk,
                        is_speech=is_speech,
                        timestamp=timestamp,
                    )

                    if (not sent_started) and segmenter.started:
                        _LOGGER.debug("Voice started")
                        write_event(
                            VoiceStarted(timestamp=segmenter.start_timestamp).event()
                        )
                        sent_started = True

                    if (not sent_stopped) and segmenter.stopped:
                        if segmenter.timeout:
                            _LOGGER.info("Voice timeout")
                        else:
                            _LOGGER.debug("Voice stopped")

                        write_event(
                            VoiceStopped(timestamp=segmenter.stop_timestamp).event()
                        )
                        sent_stopped = True

                    audio_bytes = audio_bytes[bytes_per_chunk:]
            elif AudioStart.is_type(event.type):
                _LOGGER.debug("Audio started")
                is_first_audio = True
                sent_started = False
                sent_stopped = False
                detector.reset()
                segmenter.reset()

                # Adjust time estimates
                start = AudioStart.from_event(event)
                bytes_per_chunk = args.samples_per_chunk * start.width * start.channels
                seconds_per_chunk = args.samples_per_chunk / start.rate
            elif AudioStop.is_type(event.type):
                _LOGGER.debug("Audio stopped")
                if not sent_stopped:
                    write_event(VoiceStopped(timestamp=last_stop_timestamp).event())
                    sent_stopped = True

    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------


@dataclass
class Segmenter:
    speech_seconds: float
    silence_seconds: float
    timeout_seconds: float
    reset_seconds: float
    started: bool = False
    start_timestamp: Optional[int] = None
    stopped: bool = False
    stop_timestamp: Optional[int] = None
    timeout: bool = False
    _in_command: bool = False
    _speech_seconds_left: float = 0.0
    _silence_seconds_left: float = 0.0
    _timeout_seconds_left: float = 0.0
    _reset_seconds_left: float = 0.0

    def __post_init__(self):
        self.reset()

    def reset(self):
        self._speech_seconds_left = self.speech_seconds
        self._silence_seconds_left = self.silence_seconds
        self._timeout_seconds_left = self.timeout_seconds
        self._reset_seconds_left = self.reset_seconds
        self._in_command = False
        self.start_timestamp = None
        self.stop_timestamp = None

    def process(
        self, chunk: bytes, chunk_seconds: float, is_speech: bool, timestamp: int
    ):
        self._timeout_seconds_left -= chunk_seconds
        if self._timeout_seconds_left <= 0:
            self.stop_timestamp = timestamp
            self.timeout = True
            self.stopped = True
            return

        if not self._in_command:
            if is_speech:
                self._reset_seconds_left = self.reset_seconds

                if self.start_timestamp is None:
                    self.start_timestamp = timestamp

                self._speech_seconds_left -= chunk_seconds
                if self._speech_seconds_left <= 0:
                    # Inside voice command
                    self._in_command = True
                    self.started = True
            else:
                # Reset if enough silence
                self._reset_seconds_left -= chunk_seconds
                if self._reset_seconds_left <= 0:
                    self._speech_seconds_left = self.speech_seconds
                    self.start_timestamp = None
        else:
            if not is_speech:
                self._reset_seconds_left = self.reset_seconds
                self._silence_seconds_left -= chunk_seconds
                if self._silence_seconds_left <= 0:
                    self.stop_timestamp = timestamp
                    self.stopped = True
            else:
                # Reset if enough speech
                self._reset_seconds_left -= chunk_seconds
                if self._reset_seconds_left <= 0:
                    self._silence_seconds_left = self.silence_seconds


@dataclass
class SileroDetector:
    model: Union[str, Path]
    threshold: float
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

    def is_speech(self, chunk: bytes) -> bool:
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
        return probability >= self.threshold

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
