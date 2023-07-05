#!/usr/bin/env python3
import argparse
import io
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
import socketserver
from threading import Event, Thread, Lock, Semaphore
from pathlib import Path
from typing import Dict, Final, Tuple, Optional

import numpy as np
import tflite_runtime.interpreter as tflite

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent
_MODELS_DIR = _DIR / "models"

_SAMPLE_RATE: Final = 16000  # 16Khz
_SAMPLE_WIDTH: Final = 2  # 16-bit samples
_MAX_SAMPLES: Final = 10 * _SAMPLE_RATE  # 10 seconds

_SAMPLES_PER_CHUNK: Final = 1280  # 80 ms @ 16Khz
_BYTES_PER_CHUNK: Final = _SAMPLES_PER_CHUNK * _SAMPLE_WIDTH

# window = 400, hop length = 160
_MELS_PER_SECOND: Final = 97
_MAX_MELS: Final = 10 * _MELS_PER_SECOND  # 10 seconds
_MEL_SAMPLES: Final = 1760
_NUM_MELS: Final = 32

_MAX_EMB: Final = 10 * 8  # 10 seconds
_EMB_FEATURES: Final = 76  # 775 ms
_EMB_STEP: Final = 8
_NUM_FEATURES: Final = 96

CLIENT_ID_TYPE = Tuple[str, int]


@dataclass
class WakeWordData:
    new_embeddings: int = 0
    embeddings: np.ndarray = field(
        default_factory=lambda: np.zeros(
            shape=(_MAX_EMB, _NUM_FEATURES), dtype=np.float32
        )
    )
    is_detected: bool = False
    activations: int = 0
    threshold: float = 0.5
    trigger_level: int = 4
    refractory_activations: int = 30


@dataclass
class ClientData:
    wfile: io.BufferedIOBase
    new_audio_samples: int = 0
    audio: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_SAMPLES,), dtype=np.float32)
    )
    new_mels: int = 0
    mels: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_MELS, _NUM_MELS), dtype=np.float32)
    )
    wake_words: Dict[str, WakeWordData] = field(default_factory=dict)


@dataclass
class WakeWordState:
    embeddings_ready: Semaphore = field(default_factory=Semaphore)
    embeddings_lock: Lock = field(default_factory=Lock)


@dataclass
class State:
    is_running: bool = True
    clients: Dict[str, ClientData] = field(default_factory=dict)
    clients_lock: Lock = field(default_factory=Lock)

    audio_ready: Semaphore = field(default_factory=Semaphore)
    audio_lock: Lock = field(default_factory=Lock)

    mels_ready: Semaphore = field(default_factory=Semaphore)
    mels_lock: Lock = field(default_factory=Lock)

    wake_words: Dict[str, WakeWordState] = field(default_factory=dict)


class StreamAudioHandler(socketserver.StreamRequestHandler):
    def __init__(self, state: State, *args, **kwargs):
        self._state = state
        super().__init__(*args, **kwargs)

    def handle(self):
        client_id = self.client_address
        _LOGGER.info("New client: %s", client_id)

        data = ClientData(self.wfile)
        for ww_name in self._state.wake_words:
            data.wake_words[ww_name] = WakeWordData()

        with self._state.clients_lock:
            self._state.clients[client_id] = data

        audio_bytes = bytes()

        with open("/tmp/test.raw", "wb") as f:
            try:
                while True:
                    chunk_bytes = self.request.recv(_BYTES_PER_CHUNK)
                    if not chunk_bytes:
                        # Empty chunk when client disconnects
                        break

                    f.write(chunk_bytes)

                    audio_bytes += chunk_bytes
                    while len(audio_bytes) >= _BYTES_PER_CHUNK:
                        # NOTE: Audio is *not* normalized
                        chunk_array = np.frombuffer(
                            audio_bytes[:_BYTES_PER_CHUNK], dtype=np.int16
                        ).astype(np.float32)

                        with self._state.audio_lock:
                            # Shift samples left
                            data.audio[: -len(chunk_array)] = data.audio[len(chunk_array) :]

                            # Add new samples to end
                            data.audio[-len(chunk_array) :] = chunk_array
                            data.new_audio_samples = min(
                                len(data.audio), data.new_audio_samples + len(chunk_array)
                            )

                        self._state.audio_ready.release()
                        audio_bytes = audio_bytes[_BYTES_PER_CHUNK:]
            except ConnectionResetError:
                _LOGGER.debug("Client disconnected: %s", client_id)
            except Exception:
                _LOGGER.exception("handle")
            finally:
                # Clean up
                with self._state.clients_lock:
                    self._state.clients.pop(client_id, None)


class DatagramAudioHandler(socketserver.DatagramRequestHandler):
    def __init__(self, state: State, *args, **kwargs):
        self._state = state
        self._audio_bytes = bytes()
        super().__init__(*args, **kwargs)

    def handle(self):
        client_id = self.client_address
        with self._state.clients_lock:
            data = self._state.clients.get(client_id)
            if data is None:
                _LOGGER.info("New client: %s", client_id)

                data = ClientData(self.wfile)
                for ww_name in self._state.wake_words:
                    data.wake_words[ww_name] = WakeWordData()

                self._state.clients[client_id] = data

        try:
            while True:
                chunk_bytes = self.request[0]
                if not chunk_bytes:
                    # Empty chunk when client disconnects
                    break

                self._audio_bytes += chunk_bytes
                while len(self._audio_bytes) >= _BYTES_PER_CHUNK:
                    # NOTE: Audio is *not* normalized
                    chunk_array = np.frombuffer(
                        self._audio_bytes[:_BYTES_PER_CHUNK], dtype=np.int16
                    ).astype(np.float32)

                    with self._state.audio_lock:
                        # Shift samples left
                        data.audio[: -len(chunk_array)] = data.audio[len(chunk_array) :]

                        # Add new samples to end
                        data.audio[-len(chunk_array) :] = chunk_array
                        data.new_audio_samples = min(
                            len(data.audio), data.new_audio_samples + len(chunk_array)
                        )

                    self._state.audio_ready.release()
                    self._audio_bytes = self._audio_bytes[_BYTES_PER_CHUNK:]
        except Exception:
            _LOGGER.exception("handle")
        finally:
            # Clean up
            with self._state.clients_lock:
                self._state.clients.pop(client_id, None)


# -----------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", nargs="+")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    state = State()

    # One thread per wake word model
    ww_threads: Dict[str, Thread] = {}
    for model in args.model:
        state.wake_words[model] = WakeWordState()
        ww_threads[model] = Thread(
            # target=ww_proc_no_batch,
            target=ww_proc,
            daemon=True,
            args=(
                state,
                model,
            ),
        )
        ww_threads[model].start()

    mels_thread = Thread(target=mels_proc, daemon=True, args=(state,))
    mels_thread.start()

    embeddings_thread = Thread(target=embeddings_proc, daemon=True, args=(state,))
    embeddings_thread.start()

    def make_handler(*args, **kwargs):
        return StreamAudioHandler(state, *args, **kwargs)

    try:
        with socketserver.ThreadingTCPServer(
            ("0.0.0.0", 10400), make_handler
        ) as server:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.is_running = False
        state.audio_ready.release()
        mels_thread.join()

        state.mels_ready.release()
        embeddings_thread.join()

        for ww_name, ww_state in state.wake_words.items():
            ww_state.embeddings_ready.release()
            ww_threads[ww_name].join()


# -----------------------------------------------------------------------------


def mels_proc(state: State):
    """Transform audio into mel spectrograms."""
    try:
        melspec_model_path = _MODELS_DIR / "melspectrogram.tflite"
        _LOGGER.debug("Loading %s", melspec_model_path)
        melspec_model = tflite.Interpreter(
            model_path=str(melspec_model_path), num_threads=1
        )
        melspec_input_index = melspec_model.get_input_details()[0]["index"]
        melspec_output_index = melspec_model.get_output_details()[0]["index"]

        # melspec = [batch x samples (min: 1280)] => [batch x 1 x window x mels (32)]
        # stft window size: 25ms (400)
        # stft window step: 10ms (160)
        # mel band limits: 60Hz - 3800Hz
        # mel frequency bins: 32

        while state.is_running:
            state.audio_ready.acquire()
            if not state.is_running:
                break

            while True:
                with state.audio_lock, state.clients_lock:
                    # Collect batch
                    todo_ids = [
                        client_id
                        for client_id, client in state.clients.items()
                        if client.new_audio_samples >= _MEL_SAMPLES
                    ]
                    batch_size = len(todo_ids)
                    if batch_size < 1:
                        # Not enough audio to process
                        break

                    audio_tensor = np.zeros(
                        shape=(batch_size, _MEL_SAMPLES), dtype=np.float32
                    )

                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        audio_tensor[i, :] = client.audio[
                            -client.new_audio_samples : len(client.audio)
                            - client.new_audio_samples
                            + _MEL_SAMPLES
                        ]
                        client.new_audio_samples -= _SAMPLES_PER_CHUNK

                melspec_model.resize_tensor_input(
                    melspec_input_index,
                    audio_tensor.shape,
                    strict=True,
                )
                melspec_model.allocate_tensors()

                # Generate mels
                melspec_model.set_tensor(melspec_input_index, audio_tensor)
                melspec_model.invoke()
                mels = melspec_model.get_tensor(melspec_output_index)
                mels = (mels / 10) + 2  # transform to fit embedding

                # print("Mels", mels.shape)

                num_mel_windows = mels.shape[2]
                with state.mels_lock, state.clients_lock:
                    # Add to client mels
                    for i, client_id in enumerate(todo_ids):
                        client = state.clients.get(client_id)
                        if client is None:
                            # Client disconnected
                            continue

                        # Shift
                        client.mels[:-num_mel_windows] = client.mels[num_mel_windows:]

                        # Overwrite
                        client.mels[-num_mel_windows:] = mels[i, 0, :, :]
                        client.new_mels = min(
                            len(client.mels), client.new_mels + num_mel_windows
                        )

                state.mels_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in mels thread")


# -----------------------------------------------------------------------------


def embeddings_proc(state: State):
    """Transform mels to embedding features."""
    try:
        embedding_model_path = _MODELS_DIR / "embedding_model.tflite"
        _LOGGER.debug("Loading %s", embedding_model_path)
        embedding_model = tflite.Interpreter(
            model_path=str(embedding_model_path), num_threads=1
        )
        embedding_input_index = embedding_model.get_input_details()[0]["index"]
        embedding_output_index = embedding_model.get_output_details()[0]["index"]

        # embedding = [batch x window x mels (32) x 1] => [batch x 1 x 1 x features (96)]

        while state.is_running:
            state.mels_ready.acquire()
            if not state.is_running:
                break

            while True:
                with state.mels_lock, state.clients_lock:
                    # Collect batch
                    todo_ids = [
                        client_id
                        for client_id, client in state.clients.items()
                        if client.new_mels >= _EMB_FEATURES
                    ]
                    batch_size = len(todo_ids)
                    if batch_size < 1:
                        # Not enough audio to process
                        break

                    mels_tensor = np.zeros(
                        shape=(batch_size, _EMB_FEATURES, _NUM_MELS, 1),
                        dtype=np.float32,
                    )

                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        mels_tensor[i, :, :, 0] = client.mels[
                            -client.new_mels : len(client.mels)
                            - client.new_mels
                            + _EMB_FEATURES,
                            :,
                        ]
                        client.new_mels -= _EMB_STEP

                embedding_model.resize_tensor_input(
                    embedding_input_index,
                    mels_tensor.shape,
                    strict=True,
                )
                embedding_model.allocate_tensors()

                # Generate embeddings
                embedding_model.set_tensor(embedding_input_index, mels_tensor)
                embedding_model.invoke()

                embeddings = embedding_model.get_tensor(embedding_output_index)
                # print("Embeddings", embeddings.shape)

                num_embedding_windows = embeddings.shape[2]
                with state.clients_lock:
                    for ww_name, ww_state in state.wake_words.items():
                        with ww_state.embeddings_lock:
                            # Add to wake word model embeddings
                            for i, client_id in enumerate(todo_ids):
                                client = state.clients.get(client_id)
                                if client is None:
                                    # Client disconnected
                                    continue

                                # Shift
                                client_data = client.wake_words[ww_name]
                                client_data.embeddings[
                                    :-num_embedding_windows
                                ] = client_data.embeddings[num_embedding_windows:]

                                # Overwrite
                                client_data.embeddings[
                                    -num_embedding_windows:
                                ] = embeddings[i, 0, :, :]
                                client_data.new_embeddings = min(
                                    len(client_data.embeddings),
                                    client_data.new_embeddings + num_embedding_windows,
                                )

                        ww_state.embeddings_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in embeddings thread")


# -----------------------------------------------------------------------------


def ww_proc_no_batch(state: State, ww_model_path: str):
    """Transform embedding features to wake word probabilities (no batching)."""
    try:
        _LOGGER.debug("Loading %s", ww_model_path)
        ww_model = tflite.Interpreter(model_path=str(ww_model_path), num_threads=1)
        ww_input = ww_model.get_input_details()[0]
        ww_input_shape = ww_input["shape"]
        ww_windows = ww_input_shape[1]
        ww_input_index = ww_input["index"]
        ww_output_index = ww_model.get_output_details()[0]["index"]

        # ww = [batch x window x features (96)] => [batch x probability]

        ww_state = state.wake_words[ww_model_path]
        while state.is_running:
            ww_state.embeddings_ready.acquire()
            if not state.is_running:
                break

            while True:
                todo_embeddings: Dict[str, np.ndarray] = {}
                with ww_state.embeddings_lock, state.clients_lock:
                    for client_id, client in state.clients.items():
                        if client.wake_words[ww_model_path].new_embeddings < ww_windows:
                            continue

                        embeddings_tensor = np.zeros(
                            shape=(1, ww_windows, _NUM_FEATURES),
                            dtype=np.float32,
                        )

                        client_data = client.wake_words[ww_model_path]
                        embeddings_tensor[0, :] = client_data.embeddings[
                            -client_data.new_embeddings : len(client_data.embeddings)
                            - client_data.new_embeddings
                            + ww_windows
                        ]
                        client_data.new_embeddings -= 1

                        todo_embeddings[client_id] = embeddings_tensor

                if not todo_embeddings:
                    break

                for client_id, embeddings_tensor in todo_embeddings.items():
                    ww_model.resize_tensor_input(
                        ww_input_index,
                        embeddings_tensor.shape,
                        strict=True,
                    )
                    ww_model.allocate_tensors()

                    # Generate probabilities
                    ww_model.set_tensor(ww_input_index, embeddings_tensor)
                    ww_model.invoke()
                    probabilities = ww_model.get_tensor(ww_output_index)
                    probability = probabilities[0]

                    with state.clients_lock:
                        client = state.clients.get(client_id)
                        if client is None:
                            # Client disconnected
                            continue

                        client_data = client.wake_words[ww_model_path]
                        if probability.item() >= client_data.threshold:
                            # Increase activation
                            client_data.activations += 1

                            if client_data.activations >= client_data.trigger_level:
                                client_data.is_detected = True
                                client.wfile.write(
                                    (ww_model_path + "\n").encode("utf-8")
                                )
                                client.wfile.flush()
                                _LOGGER.debug(
                                    "Triggered %s (client=%s)", ww_model_path, client_id
                                )
                                client_data.activations = (
                                    -client_data.refractory_activations
                                )
                        else:
                            # Back towards 0
                            client_data.activations = max(
                                0, client_data.activations - 1
                            )

    except Exception:
        _LOGGER.exception("Unexpected error in wake word thread")


def ww_proc(state: State, ww_model_path: str):
    """Transform embedding features to wake word probabilities (with batching)."""
    try:
        _LOGGER.debug("Loading %s", ww_model_path)
        ww_model = tflite.Interpreter(model_path=str(ww_model_path), num_threads=1)
        ww_input = ww_model.get_input_details()[0]
        ww_input_shape = ww_input["shape"]
        ww_windows = ww_input_shape[1]
        ww_input_index = ww_input["index"]
        ww_output_index = ww_model.get_output_details()[0]["index"]

        # ww = [batch x window x features (96)] => [batch x probability]

        ww_state = state.wake_words[ww_model_path]
        while state.is_running:
            ww_state.embeddings_ready.acquire()
            if not state.is_running:
                break

            while True:
                with ww_state.embeddings_lock, state.clients_lock:
                    # Collect batch
                    todo_ids = [
                        client_id
                        for client_id, client in state.clients.items()
                        if client.wake_words[ww_model_path].new_embeddings >= ww_windows
                    ]
                    batch_size = len(todo_ids)
                    if batch_size < 1:
                        # Not enough audio to process
                        break

                    embeddings_tensor = np.zeros(
                        shape=(batch_size, ww_windows, _NUM_FEATURES),
                        dtype=np.float32,
                    )

                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        client_data = client.wake_words[ww_model_path]
                        embeddings_tensor[i, :] = client_data.embeddings[
                            -client_data.new_embeddings : len(client_data.embeddings)
                            - client_data.new_embeddings
                            + ww_windows
                        ]
                        client_data.new_embeddings -= 1

                ww_model.resize_tensor_input(
                    ww_input_index,
                    embeddings_tensor.shape,
                    strict=False,  # must be False for non-dynamic batch dim
                )
                ww_model.allocate_tensors()

                # Generate probabilities
                ww_model.set_tensor(ww_input_index, embeddings_tensor)
                ww_model.invoke()
                probabilities = ww_model.get_tensor(ww_output_index)

                with state.clients_lock:
                    for i, probability in enumerate(probabilities):
                        client_id = todo_ids[i]
                        client = state.clients.get(client_id)
                        if client is None:
                            # Client disconnected
                            continue

                        client_data = client.wake_words[ww_model_path]
                        if probability.item() >= client_data.threshold:
                            # Increase activation
                            client_data.activations += 1

                            if client_data.activations >= client_data.trigger_level:
                                client_data.is_detected = True
                                client.wfile.write(
                                    (ww_model_path + "\n").encode("utf-8")
                                )
                                client.wfile.flush()
                                _LOGGER.debug(
                                    "Triggered %s (client=%s)", ww_model_path, client_id
                                )
                                client_data.activations = (
                                    -client_data.refractory_activations
                                )
                        else:
                            # Back towards 0
                            client_data.activations = max(
                                0, client_data.activations - 1
                            )

    except Exception:
        _LOGGER.exception("Unexpected error in wake word thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
