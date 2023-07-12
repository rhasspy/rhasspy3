#!/usr/bin/env python3
import argparse
import asyncio
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from threading import Event, Lock, Semaphore, Thread
from typing import Dict, Final, Optional, Tuple

from wyoming.info import Attribution, Info, WakeModel, WakeProgram
from wyoming.server import AsyncServer

from .handler import OpenWakeWordEventHandler
from .openwakeword import embeddings_proc, mels_proc, ww_proc
from .state import State, WakeWordState

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent


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
                description="An open-source audio wake word (or phrase) detection framework with a focus on performance and simplicity.",
                attribution=Attribution(
                    name="dscripka", url="https://github.com/dscripka/openWakeWord"
                ),
                installed=True,
                models=[
                    WakeModel(
                        name=model,
                        description=Path(model).stem,
                        attribution=Attribution(
                            name=model, url="https://github.com/dscripka/openWakeWord"
                        ),
                        installed=True,
                        languages=[],
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
