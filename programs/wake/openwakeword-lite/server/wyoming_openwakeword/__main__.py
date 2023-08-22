#!/usr/bin/env python3
import argparse
import asyncio
import logging
from functools import partial
from pathlib import Path
from threading import Thread
from typing import Dict, List

from wyoming.info import Attribution, Info, WakeModel, WakeProgram
from wyoming.server import AsyncServer

from .handler import OpenWakeWordEventHandler
from .openwakeword import embeddings_proc, mels_proc, ww_proc
from .state import State, WakeWordState

_LOGGER = logging.getLogger()
_DIR = Path(__file__).parent


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--model",
        required=True,
        action="append",
        help="Path to wake word model (.tflite)",
    )
    parser.add_argument(
        "--models-dir", default=_DIR / "models", help="Path to directory with models"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Wake word model threshold (0-1, default: 0.5)",
    )
    parser.add_argument(
        "--trigger-level",
        type=int,
        default=4,
        help="Number of activations before detection (default: 4)",
    )
    #
    parser.add_argument(
        "--noise-suppression",
        action="store_true",
        help="Enable noise suppression with speexdsp",
    )
    #
    parser.add_argument("--output-dir", help="Path to save audio and detections")
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument(
        "--debug-probability",
        action="store_true",
        help="Log all wake word probabilities (VERY noisy)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    _LOGGER.debug(args)

    if args.output_dir:
        # Directory to save audio clips and chunk probabilities
        args.output_dir = Path(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        _LOGGER.info("Audio and detections will be saved to %s", args.output_dir)

    # Resolve wake word model paths
    models_dir = Path(args.models_dir)
    model_paths: List[Path] = []
    for model in args.model:
        model_path = Path(model)
        if not model_path.exists():
            # Try relative to models dir
            model_path = models_dir / model

            if not model_path.exists():
                # Try with version + extension
                model_path = models_dir / f"{model}_v0.1.tflite"
                assert (
                    model_path.exists()
                ), f"Missing model: {model} (looked in: {models_dir.absolute()})"

        model_paths.append(model_path)

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
                        name=str(model_path),
                        description=model_path.stem,
                        attribution=Attribution(
                            name="dscripka",
                            url="https://github.com/dscripka/openWakeWord",
                        ),
                        installed=True,
                        languages=[],
                    )
                    for model_path in model_paths
                ],
            )
        ],
    )

    state = State(
        models_dir=models_dir,
        debug_probability=args.debug_probability,
        output_dir=args.output_dir,
    )
    loop = asyncio.get_running_loop()

    # Start server first to handle info requests
    server = AsyncServer.from_uri(args.uri)
    server_task = loop.create_task(
        server.run(partial(OpenWakeWordEventHandler, wyoming_info, args, state))
    )
    _LOGGER.debug("Server started")

    # One thread per wake word model
    ww_threads: Dict[str, Thread] = {}
    for model_path in model_paths:
        model_key = str(model_path)
        state.wake_words[model_key] = WakeWordState()
        ww_threads[model_key] = Thread(
            # target=ww_proc_no_batch,
            target=ww_proc,
            daemon=True,
            args=(
                state,
                model_key,
                loop,
            ),
        )
        ww_threads[model_key].start()

    # audio -> mels
    mels_thread = Thread(target=mels_proc, daemon=True, args=(state,))
    mels_thread.start()

    # mels -> embeddings
    embeddings_thread = Thread(target=embeddings_proc, daemon=True, args=(state,))
    embeddings_thread.start()
    _LOGGER.info("Ready")

    try:
        await server_task
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
