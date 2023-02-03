#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

from rhasspy3.core import Rhasspy
from rhasspy3.intent import recognize

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
        "--intent-program", help="Name of intent program to use (overrides pipeline)"
    )
    parser.add_argument("text", nargs="*", help="Text to recognize")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    intent_program = args.intent_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not intent_program:
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        intent_program = pipeline.intent

    assert intent_program, "No intent program"

    for text in get_texts(args):
        intent_result = await recognize(rhasspy, intent_program, text)
        if intent_result is None:
            continue

        json.dump(intent_result.event().data, sys.stdout, ensure_ascii=False)
        print("", flush=True)


def get_texts(args: argparse.Namespace) -> Iterable[str]:
    if args.text:
        for text in args.text:
            yield text
    else:
        if os.isatty(sys.stdin.fileno()):
            print("Reading text from stdin", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if line:
                yield line


if __name__ == "__main__":
    asyncio.run(main())
