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
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.intent import DOMAIN, Intent, NotRecognized, Recognize
from rhasspy3.program import create_process

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

    async with (await create_process(rhasspy, DOMAIN, intent_program)) as intent_proc:
        assert intent_proc.stdin is not None
        assert intent_proc.stdout is not None

        for text in get_texts(args):
            await async_write_event(Recognize(text=text).event(), intent_proc.stdin)
            while True:
                event = await async_read_event(intent_proc.stdout)
                if event is None:
                    sys.exit(1)

                if Intent.is_type(event.type) or NotRecognized.is_type(event.type):
                    json.dump(event.data, sys.stdout, ensure_ascii=False)
                    print("", flush=True)
                    break


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
