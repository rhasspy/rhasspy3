#!/usr/bin/env python3
"""Synthesize and speak audio."""
import argparse
import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path

from rhasspy3.core import Rhasspy
from rhasspy3.snd import play
from rhasspy3.tts import synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="*", help="Text to speak (default: stdin)")
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument("-p", "--pipeline", default="default", help="Name of pipeline")
    parser.add_argument("--tts-program", help="TTS program name")
    parser.add_argument("--snd-program", help="Audio output program name")
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=1024,
        help="Samples to send to snd program at a time",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    tts_program = args.tts_program
    snd_program = args.snd_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not tts_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        tts_program = pipeline.tts

    if not snd_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        snd_program = pipeline.snd

    assert tts_program, "No tts program"
    assert snd_program, "No snd program"

    if args.text:
        lines = args.text
    else:
        lines = sys.stdin
        if os.isatty(sys.stdin.fileno()):
            print("Reading text from stdin", file=sys.stderr)

    for line in lines:
        line = line.strip()
        if not line:
            continue

        with io.BytesIO() as wav_io:
            await synthesize(rhasspy, tts_program, line, wav_io)
            wav_io.seek(0)
            play_result = await play(
                rhasspy, snd_program, wav_io, args.samples_per_chunk
            )
            if play_result is not None:
                json.dump(
                    play_result.event().to_dict(), sys.stdout, ensure_ascii=False
                )
                print("", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
