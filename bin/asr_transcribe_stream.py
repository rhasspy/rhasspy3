#!/usr/bin/env python3
"""Transcribes raw audio from stdin into text."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from rhasspy3.asr import DOMAIN, Transcript
from rhasspy3.audio import (
    DEFAULT_IN_CHANNELS,
    DEFAULT_IN_RATE,
    DEFAULT_IN_WIDTH,
    DEFAULT_SAMPLES_PER_CHUNK,
    AudioChunk,
    AudioChunkConverter,
    AudioStart,
    AudioStop,
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
        "--mic-rate",
        type=int,
        default=DEFAULT_IN_RATE,
        help="Input sample rate (hertz)",
    )
    parser.add_argument(
        "--mic-width",
        type=int,
        default=DEFAULT_IN_WIDTH,
        help="Input sample width (bytes)",
    )
    parser.add_argument(
        "--mic-channels",
        type=int,
        default=DEFAULT_IN_CHANNELS,
        help="Input sample channel count",
    )
    #
    parser.add_argument(
        "--asr-rate", type=int, default=DEFAULT_IN_RATE, help="asr sample rate (hertz)"
    )
    parser.add_argument(
        "--asr-width",
        type=int,
        default=DEFAULT_IN_WIDTH,
        help="asr sample width (bytes)",
    )
    parser.add_argument(
        "--asr-channels",
        type=int,
        default=DEFAULT_IN_CHANNELS,
        help="asr sample channel count",
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Samples to process per chunk",
    )
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
        assert pipeline is not None, f"No pipline named {args.pipeline}"
        asr_program = pipeline.asr

    assert asr_program, "No asr program"
    _LOGGER.debug("asr program: %s", asr_program)

    # Transcribe raw audio from stdin
    converter = AudioChunkConverter(args.asr_rate, args.asr_width, args.asr_channels)
    bytes_per_chunk = args.samples_per_chunk * args.mic_width * args.mic_channels
    timestamp = 0

    async with (await create_process(rhasspy, DOMAIN, asr_program)) as asr_proc:
        assert asr_proc.stdin is not None
        assert asr_proc.stdout is not None
        _LOGGER.debug("Started %s", asr_program)

        await async_write_event(
            AudioStart(
                args.asr_rate, args.asr_width, args.asr_channels, timestamp=timestamp
            ).event(),
            asr_proc.stdin,
        )

        audio_bytes = sys.stdin.buffer.read(bytes_per_chunk)
        while audio_bytes:
            chunk = AudioChunk(
                args.mic_rate,
                args.mic_width,
                args.mic_channels,
                audio_bytes,
                timestamp=timestamp,
            )
            timestamp += chunk.milliseconds
            chunk = converter.convert(chunk)

            # Write audio
            await async_write_event(
                chunk.event(),
                asr_proc.stdin,
            )
            audio_bytes = sys.stdin.buffer.read(bytes_per_chunk)

        await async_write_event(AudioStop(timestamp=timestamp).event(), asr_proc.stdin)

        # Read transcript
        transcript = Transcript(text="")
        while True:
            event = await async_read_event(asr_proc.stdout)
            if event is None:
                break

            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                break

        json.dump(transcript.event().to_dict(), sys.stdout, ensure_ascii=False)
        print("", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
