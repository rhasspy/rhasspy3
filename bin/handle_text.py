#!/usr/bin/env python3
"""Handle text or intent."""
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

from rhasspy3.asr import Transcript
from rhasspy3.core import Rhasspy
from rhasspy3.handle import handle

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
        "--handle-program", help="Name of handle program to use (overrides pipeline)"
    )
    parser.add_argument("text", nargs="*", help="Text input to handle")
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    handle_program = args.handle_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not handle_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        handle_program = pipeline.handle

    assert handle_program, "No handle program"

    for line in get_input(args):
        # Text
        handle_input = Transcript(text=line)
        handle_result = await handle(rhasspy, handle_program, handle_input)
        if handle_result is None:
            _LOGGER.warning("No result")
            continue

        _LOGGER.debug(handle_result)
        json.dump(handle_result.event().to_dict(), sys.stdout, ensure_ascii=False)


def get_input(args: argparse.Namespace) -> Iterable[str]:
    """Get input from stdin or args."""
    if args.text:
        for text in args.text:
            yield text
    else:
        if os.isatty(sys.stdin.fileno()):
            print("Reading input from stdin", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if line:
                yield line


if __name__ == "__main__":
    asyncio.run(main())
