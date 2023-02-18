#!/usr/bin/env python3
"""Prints voice start/stop in WAV file."""
import argparse
import asyncio
import io
import json
import logging
import sys
import time
import wave
from pathlib import Path
from typing import Iterable, Optional

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.program import create_process
from rhasspy3.vad import DOMAIN, VoiceStarted, VoiceStopped

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
        "--vad-program", help="Name of vad program to use (overrides pipeline)"
    )
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Samples to process at a time",
    )
    parser.add_argument("wav", nargs="*", help="Path(s) to WAV file(s)")
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    vad_program = args.vad_program
    pipeline = rhasspy.config.pipelines.get(args.pipeline)

    if not vad_program:
        assert pipeline is not None, f"No pipeline named {args.pipeline}"
        vad_program = pipeline.vad

    assert vad_program, "No vad program"

    async with (await create_process(rhasspy, DOMAIN, vad_program)) as vad_proc:
        assert vad_proc.stdin is not None
        assert vad_proc.stdout is not None

        for wav_bytes in get_wav_bytes(args):
            with io.BytesIO(wav_bytes) as wav_io:
                with wave.open(wav_io, "rb") as wav_file:
                    rate = wav_file.getframerate()
                    width = wav_file.getsampwidth()
                    channels = wav_file.getnchannels()

                    timestamp = 0
                    await async_write_event(
                        AudioStart(rate, width, channels, timestamp=timestamp).event(),
                        vad_proc.stdin,
                    )

                    audio_bytes = wav_file.readframes(args.samples_per_chunk)
                    while audio_bytes:
                        chunk = AudioChunk(
                            rate, width, channels, audio_bytes, timestamp=timestamp
                        )
                        await async_write_event(
                            chunk.event(),
                            vad_proc.stdin,
                        )
                        timestamp += chunk.milliseconds
                        audio_bytes = wav_file.readframes(args.samples_per_chunk)

                    await async_write_event(
                        AudioStop(timestamp=timestamp).event(), vad_proc.stdin
                    )

            voice_started: Optional[VoiceStarted] = None
            voice_stopped: Optional[VoiceStopped] = None
            while True:
                event = await async_read_event(vad_proc.stdout)
                if event is None:
                    break

                if VoiceStarted.is_type(event.type):
                    voice_started = VoiceStarted.from_event(event)
                    if voice_started.timestamp is None:
                        voice_started.timestamp = time.monotonic_ns()

                    _LOGGER.debug(voice_started)
                    json.dump(
                        voice_started.event().to_dict(), sys.stdout, ensure_ascii=False
                    )
                    print("", flush=True)
                elif VoiceStopped.is_type(event.type):
                    voice_stopped = VoiceStopped.from_event(event)
                    if voice_stopped.timestamp is None:
                        voice_stopped.timestamp = time.monotonic_ns()

                    _LOGGER.debug(voice_stopped)
                    json.dump(
                        voice_stopped.event().to_dict(), sys.stdout, ensure_ascii=False
                    )
                    print("", flush=True)
                    break


def get_wav_bytes(args: argparse.Namespace) -> Iterable[bytes]:
    """Yields WAV audio from stdin or args."""
    if args.wav:
        # WAV file path(s)
        for wav_path in args.wav:
            with open(wav_path, "rb") as wav_file:
                yield wav_file.read()
    else:
        # WAV on stdin
        yield sys.stdin.buffer.read()


if __name__ == "__main__":
    asyncio.run(main())
