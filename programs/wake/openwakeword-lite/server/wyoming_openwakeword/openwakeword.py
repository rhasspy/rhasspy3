import asyncio
import logging
from typing import List

import numpy as np
import tflite_runtime.interpreter as tflite

from wyoming.wake import Detection

from .const import (
    EMB_FEATURES,
    EMB_STEP,
    MEL_SAMPLES,
    MS_PER_CHUNK,
    NUM_MELS,
    SAMPLES_PER_CHUNK,
    WW_FEATURES,
)
from .state import State

_MS_PER_CHUNK = SAMPLES_PER_CHUNK // 16

_LOGGER = logging.getLogger()


def mels_proc(state: State):
    """Transform audio into mel spectrograms."""
    try:
        melspec_model_path = state.models_dir / "melspectrogram.tflite"
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
                        if client.new_audio_samples >= MEL_SAMPLES
                    ]
                    batch_size = len(todo_ids)
                    if batch_size < 1:
                        # Not enough audio to process
                        break

                    audio_tensor = np.zeros(
                        shape=(batch_size, MEL_SAMPLES), dtype=np.float32
                    )

                    todo_timestamps: List[int] = []
                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        audio_tensor[i, :] = client.audio[
                            -client.new_audio_samples : len(client.audio)
                            - client.new_audio_samples
                            + MEL_SAMPLES
                        ]
                        client.new_audio_samples = max(
                            0, client.new_audio_samples - SAMPLES_PER_CHUNK
                        )
                        todo_timestamps.append(client.audio_timestamp)

                        # Shift timestamp
                        client.audio_timestamp += MS_PER_CHUNK

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

                        # Update timestamp
                        client.mels_timestamp = todo_timestamps[i]

                state.mels_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in mels thread")


# -----------------------------------------------------------------------------


def embeddings_proc(state: State):
    """Transform mels to embedding features."""
    try:
        embedding_model_path = state.models_dir / "embedding_model.tflite"
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
                        if client.new_mels >= EMB_FEATURES
                    ]
                    batch_size = len(todo_ids)
                    if batch_size < 1:
                        # Not enough audio to process
                        break

                    mels_tensor = np.zeros(
                        shape=(batch_size, EMB_FEATURES, NUM_MELS, 1),
                        dtype=np.float32,
                    )

                    todo_timestamps: List[int] = []
                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        mels_tensor[i, :, :, 0] = client.mels[
                            -client.new_mels : len(client.mels)
                            - client.new_mels
                            + EMB_FEATURES,
                            :,
                        ]
                        client.new_mels = max(0, client.new_mels - EMB_STEP)
                        todo_timestamps.append(client.mels_timestamp)

                        # Shift timestamp
                        client.mels_timestamp += MS_PER_CHUNK

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

                                # Update timestamp
                                client_data.embeddings_timestamp = todo_timestamps[i]

                        ww_state.embeddings_ready.release()

    except Exception:
        _LOGGER.exception("Unexpected error in embeddings thread")


# -----------------------------------------------------------------------------


def ww_proc(state: State, ww_model_path: str, loop: asyncio.AbstractEventLoop):
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
                        shape=(batch_size, ww_windows, WW_FEATURES),
                        dtype=np.float32,
                    )

                    todo_timestamps: List[int] = []
                    for i, client_id in enumerate(todo_ids):
                        client = state.clients[client_id]
                        client_data = client.wake_words[ww_model_path]
                        embeddings_tensor[i, :] = client_data.embeddings[
                            -client_data.new_embeddings : len(client_data.embeddings)
                            - client_data.new_embeddings
                            + ww_windows
                        ]
                        client_data.new_embeddings = max(
                            0, client_data.new_embeddings - 1
                        )
                        todo_timestamps.append(client_data.embeddings_timestamp)

                        # Shift timestamp
                        client_data.embeddings_timestamp += MS_PER_CHUNK

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

                coros = []
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
                                coros.append(
                                    client.event_handler.write_event(
                                        Detection(
                                            name=ww_model_path,
                                            timestamp=todo_timestamps[i],
                                        ).event()
                                    ),
                                )
                                _LOGGER.debug(
                                    "Triggered %s (client=%s)", ww_model_path, client_id
                                )
                        else:
                            # Down towards 0
                            client_data.activations = max(
                                0, client_data.activations - 1
                            )

                # Run outside lock just to be safe
                for coro in coros:
                    asyncio.run_coroutine_threadsafe(coro, loop)

    except Exception:
        _LOGGER.exception("Unexpected error in wake word thread")


# def ww_proc_no_batch(state: State, ww_model_path: str, loop: asyncio.AbstractEventLoop):
#     """Transform embedding features to wake word probabilities (no batching)."""
#     try:
#         _LOGGER.debug("Loading %s", ww_model_path)
#         ww_model = tflite.Interpreter(model_path=str(ww_model_path), num_threads=1)
#         ww_input = ww_model.get_input_details()[0]
#         ww_input_shape = ww_input["shape"]
#         ww_windows = ww_input_shape[1]
#         ww_input_index = ww_input["index"]
#         ww_output_index = ww_model.get_output_details()[0]["index"]

#         # ww = [batch x window x features (96)] => [batch x probability]

#         ww_state = state.wake_words[ww_model_path]
#         while state.is_running:
#             ww_state.embeddings_ready.acquire()
#             if not state.is_running:
#                 break

#             while True:
#                 todo_embeddings: Dict[str, np.ndarray] = {}
#                 with ww_state.embeddings_lock, state.clients_lock:
#                     for client_id, client in state.clients.items():
#                         if client.wake_words[ww_model_path].new_embeddings < ww_windows:
#                             continue

#                         embeddings_tensor = np.zeros(
#                             shape=(1, ww_windows, WW_FEATURES),
#                             dtype=np.float32,
#                         )

#                         client_data = client.wake_words[ww_model_path]
#                         embeddings_tensor[0, :] = client_data.embeddings[
#                             -client_data.new_embeddings : len(client_data.embeddings)
#                             - client_data.new_embeddings
#                             + ww_windows
#                         ]
#                         client_data.new_embeddings = max(0, client.new_embeddings - 1)

#                         todo_embeddings[client_id] = embeddings_tensor

#                 if not todo_embeddings:
#                     break

#                 for client_id, embeddings_tensor in todo_embeddings.items():
#                     ww_model.resize_tensor_input(
#                         ww_input_index,
#                         embeddings_tensor.shape,
#                         strict=True,
#                     )
#                     ww_model.allocate_tensors()

#                     # Generate probabilities
#                     ww_model.set_tensor(ww_input_index, embeddings_tensor)
#                     ww_model.invoke()
#                     probabilities = ww_model.get_tensor(ww_output_index)
#                     probability = probabilities[0]

#                     with state.clients_lock:
#                         client = state.clients.get(client_id)
#                         if client is None:
#                             # Client disconnected
#                             continue

#                         client_data = client.wake_words[ww_model_path]
#                         if probability.item() >= client_data.threshold:
#                             # Increase activation
#                             client_data.activations += 1

#                             if client_data.activations >= client_data.trigger_level:
#                                 client_data.is_detected = True
#                                 asyncio.run_coroutine_threadsafe(
#                                     client.event_handler.write_event(
#                                         Detection(name=ww_model_path).event()
#                                     ),
#                                     loop,
#                                 )
#                                 _LOGGER.debug(
#                                     "Triggered %s (client=%s)", ww_model_path, client_id
#                                 )
#                                 client_data.activations = (
#                                     -client_data.refractory_activations
#                                 )
#                         else:
#                             # Back towards 0
#                             client_data.activations = max(
#                                 0, client_data.activations - 1
#                             )

#     except Exception:
#         _LOGGER.exception("Unexpected error in wake word thread")
