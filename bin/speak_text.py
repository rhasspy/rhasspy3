#!/usr/bin/env python3
import argparse
import asyncio
import io
import logging
import sys
import wave

from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.service import create_process
from rhasspy3.audio import AudioChunk, AudioStop, AudioStart
from rhasspy3.tts import DOMAIN, Synthesize

_LOGGER = logging.getLogger("tts_text2wav")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument("-s", "--service", required=True, help="TTS service name")
    parser.add_argument("-t", "--text", required=True, help="Text to speak")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    proc = await create_process(rhasspy, DOMAIN, args.service)
    assert proc.stdin is not None
    assert proc.stdout is not None

    await async_write_event(Synthesize(text=args.text).event(), proc.stdin)

    # Wait for audio start
    while True:
        event = await async_read_event(proc.stdout)
        if event is None:
            sys.exit(1)

        if AudioStart.is_type(event.type):
            break

    _LOGGER.debug("Audio started")

    with io.BytesIO() as wav_io:
        wav_file: wave.Wave_write = wave.open(wav_io, "wb")
        with wav_file:
            first_chunk = True
            while True:
                event = await async_read_event(proc.stdout)
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    chunk = AudioChunk.from_event(event)
                    if first_chunk:
                        wav_file.setframerate(chunk.rate)
                        wav_file.setsampwidth(chunk.width)
                        wav_file.setnchannels(chunk.channels)
                        first_chunk = False
                        _LOGGER.debug("Received first chunk")

                    wav_file.writeframes(chunk.audio)
                elif AudioStop.is_type(event.type):
                    _LOGGER.debug("Audio stopped")
                    break

        sys.stdout.buffer.write(wav_io.getvalue())


if __name__ == "__main__":
    asyncio.run(main())
