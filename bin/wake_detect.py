#!/usr/bin/env python3
"""Wait for wake word to be detected."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from rhasspy3.core import Rhasspy
from rhasspy3.mic import record
from rhasspy3.wake import detect

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
        "--wake-program", help="Name of wake program to use (overrides pipeline)"
    )
    #
    parser.add_argument("--loop", action="store_true", help="Keep detecting wake words")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    wake_program = args.wake_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not mic_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        mic_program = pipeline.mic

    assert mic_program, "No mic program"
    _LOGGER.debug("mic program: %s", mic_program)

    if not wake_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        wake_program = pipeline.wake

    assert wake_program, "No wake program"
    _LOGGER.debug("wake program: %s", wake_program)

    # Detect wake word
    while True:
        async with record(rhasspy, mic_program) as mic_proc:
            assert mic_proc.stdout is not None
            _LOGGER.debug("Detecting wake word")
            detection = await detect(rhasspy, wake_program, mic_proc.stdout)
            if detection is not None:
                json.dump(detection.event().to_dict(), sys.stdout, ensure_ascii=False)
                print("", flush=True)

        if not args.loop:
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
