#!/usr/bin/env python3
"""Transcribes WAV audio into text."""
import argparse
import asyncio
import io
import json
import logging
import os
import sys
import time
import wave
from pathlib import Path
from typing import Iterable, Optional

from rhasspy3.asr import DOMAIN, Transcript
from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunkConverter,
    AudioStart,
    AudioStop,
    wav_to_chunks,
)
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
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
        "--asr-program", help="Name of asr program to use (overrides pipeline)"
    )
    #
    parser.add_argument(
        "--rate", type=int, default=DEFAULT_IN_RATE, help="Sample rate (hertz)"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_IN_WIDTH, help="Sample width (bytes)"
    )
    parser.add_argument(
        "--channels", type=int, default=DEFAULT_IN_CHANNELS, help="Sample channel count"
    )
    parser.add_argument(
        "--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK
    )
    #
    parser.add_argument("wav", nargs="*", help="Path to WAV file(s)")
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    asr_program = args.asr_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not asr_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        asr_program = pipeline.asr

    assert asr_program, "No asr program"
    _LOGGER.debug("asr program: %s", asr_program)

    # Transcribe WAV file(s)
    for wav_bytes in get_wav_bytes(args):
        converter = AudioChunkConverter(args.rate, args.width, args.channels)

        with io.BytesIO(wav_bytes) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                chunks = list(wav_to_chunks(wav_file, args.samples_per_chunk))

        async with (await create_process(rhasspy, DOMAIN, asr_program)) as asr_proc:
            assert asr_proc.stdin is not None
            assert asr_proc.stdout is not None

            # Write audio
            start_time = time.monotonic_ns()
            await async_write_event(
                AudioStart(args.rate, args.width, args.channels, timestamp=0).event(),
                asr_proc.stdin,
            )

            last_timestamp: Optional[int] = None
            for chunk in chunks:
                chunk = converter.convert(chunk)
                await async_write_event(chunk.event(), asr_proc.stdin)
                last_timestamp = chunk.timestamp

            await async_write_event(
                AudioStop(timestamp=last_timestamp).event(),
                asr_proc.stdin,
            )

            # Read transcript
            _LOGGER.debug("Waiting for transcription")
            transcript = Transcript(text="")
            while True:
                event = await async_read_event(asr_proc.stdout)
                if event is None:
                    break

                if Transcript.is_type(event.type):
                    transcript = Transcript.from_event(event)
                    end_time = time.monotonic_ns()
                    _LOGGER.debug(
                        "Transcribed in %s second(s)", (end_time - start_time) / 1e9
                    )
                    break

            _LOGGER.debug(transcript)

            json.dump(transcript.event().to_dict(), sys.stdout, ensure_ascii=False)
            print("", flush=True)


def get_wav_bytes(args: argparse.Namespace) -> Iterable[bytes]:
    """Yields WAV audio from stdin or args."""
    if args.wav:
        # WAV file path(s)
        for wav_path in args.wav:
            _LOGGER.debug("Processing %s", wav_path)
            with open(wav_path, "rb") as wav_file:
                yield wav_file.read()
    else:
        # WAV on stdin
        if os.isatty(sys.stdin.fileno()):
            print("Reading WAV audio from stdin", file=sys.stderr)

        yield sys.stdin.buffer.read()


if __name__ == "__main__":
    asyncio.run(main())
