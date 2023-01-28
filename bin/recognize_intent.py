#!/usr/bin/env python3
import argparse
import asyncio
import logging
import sys
from typing import Iterable

from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.intent import DOMAIN, Intent, NotRecognized, Recognize
from rhasspy3.program import create_process

_LOGGER = logging.getLogger("recognize_intent")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument("-p", "--program", required=True, help="Intent program name")
    parser.add_argument("text", nargs="*", help="Text to recognize")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    async with (await create_process(rhasspy, DOMAIN, args.program)) as intent_proc:
        assert intent_proc.stdin is not None
        assert intent_proc.stdout is not None

        for text in get_texts(args):
            await async_write_event(Recognize(text=text).event(), intent_proc.stdin)
            while True:
                event = await async_read_event(intent_proc.stdout)
                if event is None:
                    sys.exit(1)

                if Intent.is_type(event.type):
                    intent = Intent.from_event(event)
                    print(intent)
                    break

                if NotRecognized.is_type(event.type):
                    not_recognized = NotRecognized.from_event(event)
                    print(not_recognized)
                    break


def get_texts(args: argparse.Namespace) -> Iterable[str]:
    if args.text:
        for text in args.text:
            yield text
    else:
        for line in sys.stdin:
            line = line.strip()
            if line:
                yield line


if __name__ == "__main__":
    asyncio.run(main())
