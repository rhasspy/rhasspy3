#!/usr/bin/env python3
"""Synthesize WAV audio from text."""
import argparse
import asyncio
import io
import logging
import sys
from pathlib import Path

from rhasspy3.core import Rhasspy
from rhasspy3.tts import synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument("-p", "--pipeline", default="default", help="Name of pipeline")
    parser.add_argument("--tts-program", help="TTS program name")
    parser.add_argument("-t", "--text", required=True, help="Text to speak")
    parser.add_argument("-f", "--file", help="Write to file instead of stdout")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    tts_program = args.tts_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not tts_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        tts_program = pipeline.tts

    assert tts_program, "No tts program"

    with io.BytesIO() as wav_out:
        await synthesize(rhasspy, tts_program, args.text, wav_out)
        wav_bytes = wav_out.getvalue()

        if args.file:
            output_path = Path(args.file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(wav_bytes)
        else:
            sys.stdout.buffer.write(wav_bytes)


if __name__ == "__main__":
    asyncio.run(main())
