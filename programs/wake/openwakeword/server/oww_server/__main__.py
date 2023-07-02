#!/usr/bin/env python3
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
_SAMPLE_WIDTH = 2  # 16-bit samples
_MAX_SAMPLES = 10 * _SAMPLE_RATE  # 10 seconds

_SAMPLES_PER_CHUNK = 1280  # 80 ms @ 16Khz
_BYTES_PER_CHUNK = _SAMPLES_PER_CHUNK * _SAMPLE_WIDTH

# window = 400, hop length = 160
_MELS_PER_SECOND = 97
_MAX_MELS = 10 * _MELS_PER_SECOND  # 10 seconds
_MEL_SAMPLES = 1760
# _MEL_HOP_LENGTH = 160
_NUM_MELS = 32

_MAX_EMB = 10 * 8  # 10 seconds
_EMB_FEATURES = 76  # 775 ms
_EMB_STEP = 8
_NUM_FEATURES = 96

CLIENT_ID_TYPE = Tuple[str, int]


@dataclass
class ClientData:
    new_audio_samples: int = 0
    audio: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_SAMPLES,), dtype=np.float32)
    )
    new_mels: int = 0
    mels: np.ndarray = field(
        default_factory=lambda: np.zeros(shape=(_MAX_MELS, _NUM_MELS), dtype=np.float32)
    )
    new_embeddings: int = 0
    embeddings: np.ndarray = field(
        default_factory=lambda: np.zeros(
            shape=(_MAX_EMB, _NUM_FEATURES), dtype=np.float32
        )
    )


@dataclass
class State:
    is_running: bool = True
    clients: Dict[str, ClientData] = field(default_factory=dict)
    clients_lock: Lock = field(default_factory=Lock)

    audio_ready: Semaphore = field(default_factory=Semaphore)
    audio_lock: Lock = field(default_factory=Lock)

    mels_ready: Semaphore = field(default_factory=Semaphore)
    mels_lock: Lock = field(default_factory=Lock)

    embeddings_ready: Semaphore = field(default_factory=Semaphore)
    embeddings_lock: Lock = field(default_factory=Lock)


class AudioHandler(socketserver.BaseRequestHandler):
    def __init__(self, state: State, *args, **kwargs):
        self._state = state
        super().__init__(*args, **kwargs)

    def handle(self):
        client_id = self.client_address
        data = ClientData()
        with self._state.clients_lock:
            self._state.clients[client_id] = data

        audio_bytes = bytes()

        try:
            while True:
                chunk_bytes = self.request.recv(_BYTES_PER_CHUNK)
                if not chunk_bytes:
                    # Empty chunk when client disconnects
                    break

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
                        data.new_audio_samples += len(chunk_array)

                        # audio_array = self._state.audio_arrays.get(self.client_address)
                        # if audio_array is None:
                        #     # New array
                        #     self._state.audio_arrays[self.client_address] = chunk_array
                        # else:
                        #     # Append to existing array (resize is faster)
                        #     original_length = len(audio_array)
                        #     audio_array = np.resize(
                        #         audio_array, original_length + len(chunk_array)
                        #     )
                        #     audio_array[original_length:] = chunk_array
                        #     self._state.audio_arrays[self.client_address] = audio_array

                    self._state.audio_ready.release()
                    audio_bytes = audio_bytes[_BYTES_PER_CHUNK:]
        except Exception:
            _LOGGER.exception("handle")
        finally:
            # Clean up
            with self._state.clients_lock:
                self._state.clients.pop(client_id, None)


# -----------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    state = State()

    mels_thread = Thread(target=mels_proc, daemon=True, args=(state,))
    mels_thread.start()

    embeddings_thread = Thread(target=embeddings_proc, daemon=True, args=(state,))
    embeddings_thread.start()

    # TODO: One per ww model
    ww_thread = Thread(target=ww_proc, daemon=True, args=(state,))
    ww_thread.start()

    def make_handler(*args, **kwargs):
        return AudioHandler(state, *args, **kwargs)

    try:
        with socketserver.ThreadingTCPServer(
            ("localhost", 10400), make_handler
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

        state.embeddings_ready.release()
        ww_thread.join()


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
                # todo_ids = []
                # min_chunks = 0
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

                    # for client_id in state.audio_arrays:
                    #     client_array: Optional[np.ndarray] = state.audio_arrays[
                    #         client_id
                    #     ]
                    #     assert client_array is not None

                    #     if len(client_array) >= _MEL_SAMPLES:
                    #         todo_ids.append(client_id)

                    # num_chunks = len(client_array) // _SAMPLES_PER_CHUNK
                    # if num_chunks >= _MEL_CHUNKS:
                    #     min_chunks = (
                    #         num_chunks
                    #         if min_chunks <= 0
                    #         else min(num_chunks, min_chunks)
                    #     )
                    #     todo_ids.append(client_id)

                # batch_size = len(todo_ids)
                # if (min_chunks < _MEL_CHUNKS) or (batch_size <= 0):
                # if batch_size <= 0:
                # Not enough audio to process
                # break

                # audio_tensor = np.zeros(
                #     shape=(batch_size, min_chunks * _SAMPLES_PER_CHUNK), dtype=np.float32
                # )
                # audio_tensor = np.zeros(
                #     shape=(batch_size, _MEL_SAMPLES), dtype=np.float32
                # )
                melspec_model.resize_tensor_input(
                    melspec_input_index,
                    audio_tensor.shape,
                    strict=True,
                )
                melspec_model.allocate_tensors()

                # with state.audio_lock:
                #     # Copy audio data over now
                #     for i, client_id in enumerate(todo_ids):
                #         client_array = state.audio_arrays.get(client_id)
                #         if client_array is None:
                #             # Client may have disconnected
                #             continue

                #         audio_tensor[i, :] = client_array[: audio_tensor.shape[1]]

                #         # Remove processed chunk from client array
                #         # TODO: Is the hop length used here correctly?
                #         state.audio_arrays[client_id] = client_array[
                #             # audio_tensor.shape[1]
                #             # - _MEL_HOP_LENGTH :
                #             # _MEL_SAMPLES:
                #             _SAMPLES_PER_CHUNK:
                #         ]

                # Generate mels
                melspec_model.set_tensor(melspec_input_index, audio_tensor)
                melspec_model.invoke()
                mels = melspec_model.get_tensor(melspec_output_index)
                mels = (mels / 10) + 2  # transform to fit embedding

                print("Mels", mels.shape)

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
                        client.new_mels += num_mel_windows

                #         if client_mels is None:
                #             state.mels[client_id] = mels[i, :, :, :]
                #         else:
                #             original_length = client_mels.shape[1]
                #             client_mels = np.resize(
                #                 client_mels,
                #                 (
                #                     mels.shape[1],
                #                     original_length + mels.shape[2],
                #                     mels.shape[3],
                #                 ),
                #             )
                #             assert client_mels is not None
                #             client_mels[0, original_length:, :] = mels[i, :, :, :]
                #             state.mels[client_id] = client_mels

                state.mels_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in mels thread")


# -----------------------------------------------------------------------------


def embeddings_proc(state: State):
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
                # todo_ids = []
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

                # batch_size = len(todo_ids)
                # if batch_size <= 0:
                #     # Not enough embedding features to process
                #     break

                # mels_tensor = np.zeros(
                #     shape=(batch_size, _EMB_FEATURES, _NUM_MELS, 1), dtype=np.float32
                # )
                # embedding_model.resize_tensor_input(
                #     embedding_input_index,
                #     mels_tensor.shape,
                #     strict=True,
                # )
                # embedding_model.allocate_tensors()

                # with state.mels_lock:
                #     # Copy mel data over now
                #     for i, client_id in enumerate(todo_ids):
                #         client_mels = state.mels.get(client_id)
                #         if client_mels is None:
                #             # Client may have disconnected
                #             continue

                #         mels_tensor[i, :, :, 0] = client_mels[
                #             0,
                #             : mels_tensor.shape[1],
                #             :,
                #         ]

                #         # Remove processed mels
                #         state.mels[client_id] = client_mels[
                #             0,
                #             _EMB_STEP:,
                #             :,
                #         ]

                # Generate embeddings
                embedding_model.set_tensor(embedding_input_index, mels_tensor)
                embedding_model.invoke()

                embeddings = embedding_model.get_tensor(embedding_output_index)
                print("Embeddings", embeddings.shape)

                num_embedding_windows = embeddings.shape[2]
                with state.embeddings_lock, state.clients_lock:
                    # Add to client embeddings
                    for i, client_id in enumerate(todo_ids):
                        client = state.clients.get(client_id)
                        if client is None:
                            # Client disconnected
                            continue

                        # Shift
                        client.embeddings[:-num_embedding_windows] = client.embeddings[
                            num_embedding_windows:
                        ]

                        # Overwrite
                        client.embeddings[-num_embedding_windows:] = embeddings[
                            i, 0, :, :
                        ]
                        client.new_embeddings += num_embedding_windows

                # with state.embeddings_lock:
                #     # Add to client embeddings
                #     for i, client_id in enumerate(todo_ids):
                #         client_embeddings = state.embeddings.get(client_id)
                #         if client_embeddings is None:
                #             # 1 window
                #             state.embeddings[client_id] = np.resize(
                #                 embeddings[i, 0, 0, :], (1, embeddings.shape[-1])
                #             )
                #         else:
                #             # 1 more window
                #             original_length = client_embeddings.shape[-1]
                #             client_embeddings = np.resize(
                #                 client_embeddings,
                #                 (original_length + 1, embeddings.shape[-1]),
                #             )
                #             assert client_embeddings is not None
                #             client_embeddings[original_length:, :] = embeddings[
                #                 i, 0, 0, :
                #             ]
                #             state.embeddings[client_id] = client_embeddings

                state.embeddings_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in embeddings thread")


# -----------------------------------------------------------------------------


def ww_proc(state: State):
    try:
        ww_model_path = _MODELS_DIR / "alexa_v0.1.tflite"
        _LOGGER.debug("Loading %s", ww_model_path)
        ww_model = tflite.Interpreter(model_path=str(ww_model_path), num_threads=1)
        ww_input = ww_model.get_input_details()[0]
        ww_input_shape = ww_input["shape"]
        ww_windows = ww_input_shape[1]
        ww_input_index = ww_input["index"]
        ww_output_index = ww_model.get_output_details()[0]["index"]

        # ww = [batch x window x features (96)] => [batch x probability]

        while state.is_running:
            state.embeddings_ready.acquire()
            if not state.is_running:
                break

            while True:
                with state.embeddings_lock, state.clients_lock:
                    # Collect batch
                    todo_ids = [
                        client_id
                        for client_id, client in state.clients.items()
                        if client.new_embeddings >= ww_windows
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
                        embeddings_tensor[i, :] = client.embeddings[
                            -client.new_embeddings : len(client.embeddings)
                            - client.new_embeddings
                            + ww_windows
                        ]
                        client.new_embeddings -= 1

                batch_size = len(todo_ids)
                if batch_size <= 0:
                    # Not enough embedding features to process
                    break

                # HACK
                # batch_size = 1
                # todo_ids = todo_ids[:1]

                ww_model.resize_tensor_input(
                    ww_input_index,
                    embeddings_tensor.shape,
                    strict=True,
                )
                ww_model.allocate_tensors()

                # with state.clients_lock:
                #     for i, client_id in enumerate(todo_ids):
                #         client = state.clients.get(client_id)
                #         if client is None:
                #             # Client disconnected
                #             continue

                #         # Shift
                #         client.embeddings[:-num_embedding_windows] = client.embeddings[
                #             num_embedding_windows:
                #         ]

                #         # Overwrite
                #         client.embeddings[-num_embedding_windows:] = embeddings[
                #             i, 0, :, :
                #         ]
                #         client.new_embeddings += num_embedding_windows

                # with state.embeddings_lock, state.clients_lock:
                #     # Copy embeddings data over now
                #     for i, client_id in enumerate(todo_ids):
                #         client_embeddings = state.embeddings.get(client_id)
                #         if client_embeddings is None:
                #             # Client may have disconnected
                #             continue

                #         embeddings_tensor[i, :, :] = client_embeddings[
                #             : embeddings_tensor.shape[1],
                #             :,
                #         ]

                #         # Remove 1 embedding
                #         state.embeddings[client_id] = client_embeddings[
                #             1:,
                #             :,
                #         ]

                # Generate probabilities
                ww_model.set_tensor(ww_input_index, embeddings_tensor)
                ww_model.invoke()
                probabilities = ww_model.get_tensor(ww_output_index)
                print("Probabilities", probabilities)

    except Exception:
        _LOGGER.exception("Unexpected error in wake word thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
