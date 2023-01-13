#!/usr/bin/env python3
import argparse
import asyncio
import logging
import io
import sys
import wave
from typing import Iterable, Optional

from rhasspy3.core import Rhasspy
from rhasspy3.event import async_read_event, async_write_event
from rhasspy3.program import create_process
from rhasspy3.audio import AudioChunk, AudioStop, AudioStart
from rhasspy3.asr import DOMAIN, Transcript

_LOGGER = logging.getLogger("transcribe_wav")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Configuration directory",
    )
    parser.add_argument("-n", "--name", required=True, help="ASR program name")
    parser.add_argument("wav", nargs="*", help="Path(s) to WAV file(s)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    rhasspy = Rhasspy.load(args.config)

    for wav_bytes in get_wav_bytes(args):
        with io.BytesIO(wav_bytes) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                num_frames = wav_file.getnframes()
                wav_seconds = num_frames / rate
                timestamp = int(wav_seconds * 1_000)
                audio_bytes = wav_file.readframes(num_frames)

        proc = await create_process(rhasspy, DOMAIN, args.name)
        assert proc.stdin is not None
        assert proc.stdout is not None

        await async_write_event(AudioStart(timestamp=0).event(), proc.stdin)
        await async_write_event(
            AudioChunk(rate, width, channels, audio_bytes, timestamp=0).event(),
            proc.stdin,
        )
        await async_write_event(AudioStop(timestamp=timestamp).event(), proc.stdin)

        transcript: Optional[Transcript] = None
        while True:
            event = await async_read_event(proc.stdout)
            if event is None:
                break

            if Transcript.is_type(event.type):
                transcript = Transcript.from_event(event)
                break

        if transcript is not None:
            print(transcript.text)
        else:
            # No transcript
            print("")


def get_wav_bytes(args: argparse.Namespace) -> Iterable[bytes]:
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
