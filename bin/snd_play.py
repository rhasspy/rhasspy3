#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK
from rhasspy3.core import Rhasspy
from rhasspy3.snd import play

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_file", nargs="*", help="Path to WAV file(s) to play")
    parser.add_argument(
        "-c",
        "--config",
        default=_DIR.parent / "config",
        help="Configuration directory",
    )
    parser.add_argument("-p", "--pipeline", default="default", help="Name of pipeline")
    parser.add_argument("--snd-program", help="Audio output program name")
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Samples to send to snd program at a time",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    snd_program = args.snd_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not snd_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        snd_program = pipeline.snd

    assert snd_program, "No snd program"

    if args.wav_file:
        for wav_path in args.wav_file:
            with open(wav_path, "rb") as wav_file:
                await play(
                    rhasspy, snd_program, wav_file, args.samples_per_chunk, sleep=True
                )
    else:
        if os.isatty(sys.stdin.fileno()):
            print("Reading WAV data from stdin", file=sys.stderr)

        await play(
            rhasspy,
            snd_program,
            sys.stdin.buffer,
            args.samples_per_chunk,
            sleep=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
