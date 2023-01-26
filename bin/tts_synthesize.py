#!/usr/bin/env python3
import argparse
import asyncio
import io
import logging
import sys

from rhasspy3.core import Rhasspy
from rhasspy3.tts import synthesize

_LOGGER = logging.getLogger("speak_text")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument("-p", "--program", required=True, help="TTS program name")
    parser.add_argument("-t", "--text", required=True, help="Text to speak")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    with io.BytesIO() as wav_out:
        await synthesize(rhasspy, args.program, args.text, wav_out)
        sys.stdout.buffer.write(wav_out.getvalue())


if __name__ == "__main__":
    asyncio.run(main())
