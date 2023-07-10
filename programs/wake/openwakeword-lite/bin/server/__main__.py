#!/usr/bin/env python3
import argparse
import asyncio
import logging
import threading
from functools import partial
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Event, Thread, Lock, Semaphore
from pathlib import Path
from typing import Dict, Final, Tuple, Optional

from wyoming.info import Attribution, Info, WakeModel, WakeProgram
from wyoming.server import AsyncServer

from .handler import OpenWakeWordEventHandler
from .openwakeword import mels_proc, ww_proc, embeddings_proc
from .state import State, WakeWordState

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent


# class StreamAudioHandler(socketserver.StreamRequestHandler):
#     def __init__(self, state: State, *args, **kwargs):
#         self._state = state
#         super().__init__(*args, **kwargs)

#     def handle(self):
#         client_id = self.client_address
#         _LOGGER.info("New client: %s", client_id)

#         data = ClientData(self.wfile)
#         for ww_name in self._state.wake_words:
#             data.wake_words[ww_name] = WakeWordData()

#         with self._state.clients_lock:
#             self._state.clients[client_id] = data

#         audio_bytes = bytes()

#         with open("/tmp/test.raw", "wb") as f:
#             try:
#                 while True:
#                     chunk_bytes = self.request.recv(_BYTES_PER_CHUNK)
#                     if not chunk_bytes:
#                         # Empty chunk when client disconnects
#                         break

#                     f.write(chunk_bytes)

#                     audio_bytes += chunk_bytes
#                     while len(audio_bytes) >= _BYTES_PER_CHUNK:
#                         # NOTE: Audio is *not* normalized
#                         chunk_array = np.frombuffer(
#                             audio_bytes[:_BYTES_PER_CHUNK], dtype=np.int16
#                         ).astype(np.float32)

#                         with self._state.audio_lock:
#                             # Shift samples left
#                             data.audio[: -len(chunk_array)] = data.audio[
#                                 len(chunk_array) :
#                             ]

#                             # Add new samples to end
#                             data.audio[-len(chunk_array) :] = chunk_array
#                             data.new_audio_samples = min(
#                                 len(data.audio),
#                                 data.new_audio_samples + len(chunk_array),
#                             )

#                         self._state.audio_ready.release()
#                         audio_bytes = audio_bytes[_BYTES_PER_CHUNK:]
#             except ConnectionResetError:
#                 _LOGGER.debug("Client disconnected: %s", client_id)
#             except Exception:
#                 _LOGGER.exception("handle")
#             finally:
#                 # Clean up
#                 with self._state.clients_lock:
#                     self._state.clients.pop(client_id, None)


# -----------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        help="Path to wake word model (.tflite)",
    )
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    wyoming_info = Info(
        wake=[
            WakeProgram(
                name="openwakeword",
                attribution=Attribution(
                    name="dscripka", url="https://github.com/dscripka/openWakeWord"
                ),
                installed=True,
                models=[
                    WakeModel(
                        name=model,
                        attribution=Attribution(
                            name=model, url="https://github.com/dscripka/openWakeWord"
                        ),
                        installed=True,
                        languages=["en"],  # HACK
                    )
                    for model in args.model
                ],
            )
        ],
    )

    state = State(models_dir=_DIR.parent.parent / "share")

    # One thread per wake word model
    loop = asyncio.get_running_loop()
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
                loop,
            ),
        )
        ww_threads[model].start()

    # audio -> mels
    mels_thread = Thread(target=mels_proc, daemon=True, args=(state,))
    mels_thread.start()

    # mels -> embeddings
    embeddings_thread = Thread(target=embeddings_proc, daemon=True, args=(state,))
    embeddings_thread.start()

    server = AsyncServer.from_uri(args.uri)

    try:
        await server.run(partial(OpenWakeWordEventHandler, wyoming_info, args, state))
    except KeyboardInterrupt:
        pass
    finally:
        # Graceful shutdown
        _LOGGER.debug("Shutting down")
        state.is_running = False
        state.audio_ready.release()
        mels_thread.join()

        state.mels_ready.release()
        embeddings_thread.join()

        for ww_name, ww_state in state.wake_words.items():
            ww_state.embeddings_ready.release()
            ww_threads[ww_name].join()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
