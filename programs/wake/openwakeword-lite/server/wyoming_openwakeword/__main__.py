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
        help="Name or path to wake word model (.tflite)",
    )
    parser.add_argument(
        "--models-dir", default=_DIR / "models", help="Path to directory with models"
    )
    parser.add_argument(
        "--preload-model",
        action="append",
        default=[],
        help="Name or path of wake word model(s) to pre-load",
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
        default=1,
        help="Number of activations before detection (default: 4)",
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
        _LOGGER.info("Audio will be saved to %s", args.output_dir)

    # Resolve wake word model paths
    models_dir = Path(args.models_dir)
    state = State(
        models_dir=models_dir,
        debug_probability=args.debug_probability,
        output_dir=args.output_dir,
    )

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

        state.model_paths[model] = model_path

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
                        name=model_key,
                        # hey_jarvis_v0.1 => hey jarvis
                        description=" ".join(model_path.stem.split("_")[:-1]),
                        attribution=Attribution(
                            name="dscripka",
                            url="https://github.com/dscripka/openWakeWord",
                        ),
                        installed=True,
                        languages=[],
                    )
                    for model_key, model_path in state.model_paths.items()
                ],
            )
        ],
    )

    loop = asyncio.get_running_loop()

    # One thread per wake word model
    for model_key in args.preload_model:
        model_path = state.model_paths.get(model_key)
        if model_path is None:
            raise ValueError(f"Cannot preload model: {model_key}")

        state.wake_words[model_key] = WakeWordState()
        state.ww_threads[model_key] = Thread(
            target=ww_proc,
            daemon=True,
            args=(
                state,
                model_key,
                model_path,
                loop,
            ),
        )
        state.ww_threads[model_key].start()

    # audio -> mels
    mels_thread = Thread(target=mels_proc, daemon=True, args=(state,))
    mels_thread.start()

    # mels -> embeddings
    embeddings_thread = Thread(target=embeddings_proc, daemon=True, args=(state,))
    embeddings_thread.start()
    _LOGGER.info("Ready")

    # Start server
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
            state.ww_threads[ww_name].join()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
