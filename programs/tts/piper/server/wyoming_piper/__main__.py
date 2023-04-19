#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import tempfile
from functools import partial
from pathlib import Path
from typing import Optional

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from .download import download_voice, find_voice
from .handler import PiperEventHandler

_LOGGER = logging.getLogger(__name__)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--piper",
        required=True,
        help="Path to piper executable",
    )
    parser.add_argument(
        "--voice",
        required=True,
        help="Name of Piper voice to use (e.g., en-us-ryan-low)",
    )
    parser.add_argument("--uri", required=True, help="unix:// or tcp://")
    parser.add_argument(
        "--data-dir",
        required=True,
        action="append",
        help="Data directory to check for downloaded models",
    )
    parser.add_argument(
        "--download-dir",
        required=True,
        help="Directory to download voices into",
    )
    #
    parser.add_argument("--speaker", type=int, help="Id of speaker (default: 0)")
    parser.add_argument("--noise-scale", type=float, help="Generator noise")
    parser.add_argument("--length-scale", type=float, help="Phoneme length")
    parser.add_argument("--noise-w", type=float, help="Phoneme width noise")
    #
    parser.add_argument(
        "--auto-punctuation", default=".?!", help="Automatically add punctuation"
    )
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Look for voice
    voice_onnx: Optional[Path] = None
    for data_dir in args.data_dir:
        voice_onnx = find_voice(args.voice, data_dir)
        if voice_onnx is not None:
            break

    if voice_onnx is None:
        _LOGGER.info("Downloading %s to %s", args.voice, args.download_dir)
        voice_onnx = download_voice(args.voice, args.download_dir)

    # Load voice info
    voice_config_path = f"{voice_onnx}.json"
    with open(voice_config_path, "r", encoding="utf-8") as voice_config_file:
        voice_config = json.load(voice_config_file)

    num_speakers = voice_config["num_speakers"]
    voice_language = voice_config["espeak"]["voice"]
    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="piper",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/piper"
                ),
                installed=True,
                voices=[
                    TtsVoice(
                        name=args.voice,
                        attribution=Attribution(
                            name="rhasspy", url="https://github.com/rhasspy/piper"
                        ),
                        installed=True,
                        languages=[voice_language],
                    )
                ],
            )
        ],
    )

    server = AsyncServer.from_uri(args.uri)

    with tempfile.TemporaryDirectory() as temp_dir:
        piper_args = [
            "--model",
            str(voice_onnx),
            "--output_dir",
            str(temp_dir),
        ]

        if (args.speaker is not None) and (num_speakers > 1):
            piper_args.extend(["--speaker", str(args.speaker)])

        if args.noise_scale:
            piper_args.extend(["--noise-scale", str(args.noise_scale)])

        if args.length_scale:
            piper_args.extend(["--length-scale", str(args.length_scale)])

        if args.noise_w:
            piper_args.extend(["--noise-w", str(args.noise_w)])

        proc = await asyncio.create_subprocess_exec(
            args.piper,
            *piper_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        _LOGGER.info("Ready")
        proc_lock = asyncio.Lock()
        await server.run(
            partial(
                PiperEventHandler,
                wyoming_info,
                args,
                proc,
                proc_lock,
            )
        )


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
