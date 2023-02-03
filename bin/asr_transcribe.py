#!/usr/bin/env python3
"""Transcribes mic audio into text."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from rhasspy3.asr import DOMAIN, Transcript
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.core import Rhasspy
from rhasspy3.program import create_process
from rhasspy3.vad import segment
from rhasspy3.event import async_read_event

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
    parser.add_argument(
        "-p", "--pipeline", default="default", help="Name of pipeline to use"
    )
    parser.add_argument(
        "--mic-program", help="Name of mic program to use (overrides pipeline)"
    )
    parser.add_argument(
        "--asr-program", help="Name of asr program to use (overrides pipeline)"
    )
    parser.add_argument(
        "--vad-program", help="Name of vad program to use (overrides pipeline)"
    )
    #
    parser.add_argument(
        "--output-json", action="store_true", help="Outputs JSON instead of text"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    asr_program = args.asr_program
    vad_program = args.vad_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"

    if not asr_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        asr_program = pipeline.asr

    assert asr_program, "No asr program"

    if not vad_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        vad_program = pipeline.vad

    assert vad_program, "No vad program"

    # Transcribe voice command
    async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc, (
        await create_process(rhasspy, DOMAIN, asr_program)
    ) as asr_proc:
        assert mic_proc.stdout is not None
        assert asr_proc.stdin is not None
        assert asr_proc.stdout is not None

        _LOGGER.info("Ready")
        await segment(rhasspy, vad_program, mic_proc.stdout, asr_proc.stdin)

        # Read transcript
        transcript = Transcript(text="")
        while True:
            event = await async_read_event(asr_proc.stdout)
            if event is None:
                break

            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                break

        if args.output_json:
            # JSON output
            json.dump(transcript.event().data, sys.stdout)
            print("", flush=True)
        else:
            # Text output
            print(transcript.text or "", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
