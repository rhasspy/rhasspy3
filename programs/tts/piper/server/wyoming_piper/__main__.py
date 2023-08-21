#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
from functools import partial
from pathlib import Path
from typing import Any, Dict, Set

from wyoming.info import Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer

from .download import find_voice, get_voices
from .handler import PiperEventHandler
from .process import PiperProcessManager

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
        help="Default Piper voice to use (e.g., en_US-lessac-medium)",
    )
    parser.add_argument("--uri", default="stdio://", help="unix:// or tcp://")
    parser.add_argument(
        "--data-dir",
        required=True,
        action="append",
        help="Data directory to check for downloaded models",
    )
    parser.add_argument(
        "--download-dir",
        help="Directory to download voices into (default: first data dir)",
    )
    #
    parser.add_argument(
        "--speaker", type=str, help="Name or id of speaker for default voice"
    )
    parser.add_argument("--noise-scale", type=float, help="Generator noise")
    parser.add_argument("--length-scale", type=float, help="Phoneme length")
    parser.add_argument("--noise-w", type=float, help="Phoneme width noise")
    #
    parser.add_argument(
        "--auto-punctuation", default=".?!", help="Automatically add punctuation"
    )
    parser.add_argument("--samples-per-chunk", type=int, default=1024)
    parser.add_argument(
        "--max-piper-procs",
        type=int,
        default=1,
        help="Maximum number of piper process to run simultaneously (default: 1)",
    )
    #
    parser.add_argument(
        "--update-voices",
        action="store_true",
        help="Download latest voices.json during startup",
    )
    #
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    if not args.download_dir:
        # Default to first data directory
        args.download_dir = args.data_dir[0]

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Load voice info
    voices_info = get_voices(args.download_dir, update_voices=args.update_voices)

    # Resolve aliases for backwards compatibility with old voice names
    aliases_info: Dict[str, Any] = {}
    for voice_info in voices_info.values():
        for voice_alias in voice_info.get("aliases", []):
            aliases_info[voice_alias] = {"_is_alias": True, **voice_info}

    voices_info.update(aliases_info)
    voices = [
        TtsVoice(
            name=voice_name,
            description=get_description(voice_info),
            attribution=Attribution(
                name="rhasspy", url="https://github.com/rhasspy/piper"
            ),
            installed=True,
            languages=[voice_info["language"]["code"]],
            #
            # Don't send speakers for now because it overflows StreamReader buffers
            # speakers=[
            #     TtsVoiceSpeaker(name=speaker_name)
            #     for speaker_name in voice_info["speaker_id_map"]
            # ]
            # if voice_info.get("speaker_id_map")
            # else None,
        )
        for voice_name, voice_info in voices_info.items()
        if not voice_info.get("_is_alias", False)
    ]

    custom_voice_names: Set[str] = set()
    if args.voice not in voices_info:
        custom_voice_names.add(args.voice)

    for data_dir in args.data_dir:
        data_dir = Path(data_dir)
        if not data_dir.is_dir():
            continue

        for onnx_path in data_dir.glob("*.onnx"):
            custom_voice_name = onnx_path.stem
            if custom_voice_name not in voices_info:
                custom_voice_names.add(custom_voice_name)

    for custom_voice_name in custom_voice_names:
        # Add custom voice info
        _custom_voice_path, custom_config_path = find_voice(
            custom_voice_name, args.data_dir
        )
        with open(custom_config_path, "r", encoding="utf-8") as custom_config_file:
            custom_config = json.load(custom_config_file)
            custom_name = custom_config["dataset"]
            custom_quality = custom_config["audio"]["quality"]
            voices.append(
                TtsVoice(
                    name=custom_name,
                    description=f"{custom_name} ({custom_quality})",
                    attribution=Attribution(name="", url=""),
                    installed=True,
                    languages=[custom_config["language"]["code"]],
                )
            )

    wyoming_info = Info(
        tts=[
            TtsProgram(
                name="piper",
                description="A fast, local, neural text to speech engine",
                attribution=Attribution(
                    name="rhasspy", url="https://github.com/rhasspy/piper"
                ),
                installed=True,
                voices=sorted(voices, key=lambda v: v.name),
            )
        ],
    )

    process_manager = PiperProcessManager(args, voices_info)

    # Make sure default voice is loaded.
    # Other voices will be loaded on-demand.
    await process_manager.get_process()

    # Start server
    server = AsyncServer.from_uri(args.uri)

    _LOGGER.info("Ready")
    await server.run(
        partial(
            PiperEventHandler,
            wyoming_info,
            args,
            process_manager,
        )
    )


# -----------------------------------------------------------------------------


def get_description(voice_info: Dict[str, Any]):
    """Get a human readable description for a voice."""
    name = voice_info["name"]
    name = " ".join(name.split("_"))
    quality = voice_info["quality"]

    return f"{name} ({quality})"


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
