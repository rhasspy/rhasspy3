#!/usr/bin/env python3
"""Prints voice start/stop in WAV file."""
import argparse
import asyncio
import io
import json
import logging
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.program import create_process
from rhasspy3.vad import DOMAIN as VAD_DOMAIN, VoiceStarted, VoiceStopped
from rhasspy3.mic import DOMAIN as MIC_DOMAIN

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
        "--vad-program", help="Name of vad program to use (overrides pipeline)"
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Samples to process at a time",
    )
    parser.add_argument(
        "--loop", action="store_true", help="Keep running after speech has stopped"
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    vad_program = args.vad_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"

    if not vad_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        vad_program = pipeline.vad

    assert vad_program, "No vad program"

    while True:
        async with (
            await create_process(rhasspy, MIC_DOMAIN, mic_program)
        ) as mic_proc, (
            await create_process(rhasspy, VAD_DOMAIN, vad_program)
        ) as vad_proc:
            assert mic_proc.stdin is not None
            assert mic_proc.stdout is not None
            assert vad_proc.stdin is not None
            assert vad_proc.stdout is not None

            mic_task = asyncio.create_task(async_read_event(mic_proc.stdout))
            vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
            pending = {mic_task, vad_task}

            while True:
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED
                )
                if mic_task in done:
                    mic_event = mic_task.result()
                    if mic_event is None:
                        break

                    if AudioChunk.is_type(mic_event.type):
                        await async_write_event(mic_event, vad_proc.stdin)

                    # Next chunk
                    mic_task = asyncio.create_task(async_read_event(mic_proc.stdout))
                    pending.add(mic_task)

                if vad_task in done:
                    vad_event = vad_task.result()
                    if vad_event is None:
                        break

                    json.dump(vad_event.to_dict(), sys.stdout, ensure_ascii=False)
                    print("", flush=True)

                    if VoiceStopped.is_type(vad_event.type):
                        if mic_task in pending:
                            # Clear pending task
                            await mic_task

                        # Stop mic and vad
                        await async_write_event(AudioStop().event(), mic_proc.stdin)
                        await async_write_event(AudioStop().event(), vad_proc.stdin)
                        break

                    # Next VAD event
                    vad_task = asyncio.create_task(async_read_event(vad_proc.stdout))
                    pending.add(vad_task)

            if not args.loop:
                break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
