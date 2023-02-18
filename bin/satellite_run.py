#!/usr/bin/env python3
"""Run satellite loop."""
import argparse
import asyncio
import logging
from collections import deque
from pathlib import Path
from typing import Deque, List

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.core import Rhasspy
from rhasspy3.event import Event, async_read_event, async_write_event
from rhasspy3.mic import DOMAIN as MIC_DOMAIN
from rhasspy3.program import create_process
from rhasspy3.remote import DOMAIN as REMOTE_DOMAIN
from rhasspy3.snd import DOMAIN as SND_DOMAIN
from rhasspy3.snd import Played
from rhasspy3.wake import detect

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
        "-s", "--satellite", default="default", help="Name of satellite to use"
    )
    #
    parser.add_argument(
        "--mic-program",
        help="Program to use for mic input (overrides satellite)",
    )
    parser.add_argument(
        "--wake-program",
        help="Program to use for wake word detection (overiddes satellite)",
    )
    parser.add_argument(
        "--remote-program",
        help="Program to use for remote communication with base station (overrides satellite)",
    )
    parser.add_argument(
        "--snd-program",
        help="Program to use for audio output (overrides satellite)",
    )
    #
    parser.add_argument("--asr-chunks-to-buffer", type=int, default=0)
    #
    parser.add_argument("--loop", action="store_true", help="Keep satellite running")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    rhasspy = Rhasspy.load(args.config)
    mic_program = args.mic_program
    wake_program = args.wake_program
    remote_program = args.remote_program
    snd_program = args.snd_program
    satellite = rhasspy.config.satellites.get(args.satellite)

    if not mic_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        mic_program = satellite.mic

    assert mic_program, "No mic program"

    if not wake_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        wake_program = satellite.asr

    assert wake_program, "No wake program"

    if not remote_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        remote_program = satellite.remote

    assert remote_program, "No remote program"

    if not snd_program:
        assert satellite is not None, f"No satellite named {args.satellite}"
        snd_program = satellite.snd

    assert snd_program, "No snd program"

    while True:
        chunk_buffer: Deque[Event] = deque(maxlen=args.asr_chunks_to_buffer)
        snd_buffer: List[Event] = []

        async with (await create_process(rhasspy, MIC_DOMAIN, mic_program)) as mic_proc:
            assert mic_proc.stdout is not None

            detection = await detect(
                rhasspy, wake_program, mic_proc.stdout, chunk_buffer
            )
            if detection is None:
                continue

            async with (
                await create_process(rhasspy, REMOTE_DOMAIN, remote_program)
            ) as remote_proc:
                assert remote_proc.stdin is not None
                assert remote_proc.stdout is not None

                while chunk_buffer:
                    await async_write_event(chunk_buffer.pop(), remote_proc.stdin)

                mic_task = asyncio.create_task(async_read_event(mic_proc.stdout))
                remote_task = asyncio.create_task(async_read_event(remote_proc.stdout))
                pending = {mic_task, remote_task}

                try:
                    # Stream to remote until audio is received
                    while True:
                        done, pending = await asyncio.wait(
                            pending, return_when=asyncio.FIRST_COMPLETED
                        )

                        if mic_task in done:
                            mic_event = mic_task.result()
                            if mic_event is None:
                                break

                            if AudioChunk.is_type(mic_event.type):
                                await async_write_event(mic_event, remote_proc.stdin)

                            mic_task = asyncio.create_task(
                                async_read_event(mic_proc.stdout)
                            )
                            pending.add(mic_task)

                        if remote_task in done:
                            remote_event = remote_task.result()
                            if remote_event is not None:
                                snd_buffer.append(remote_event)

                            for task in pending:
                                task.cancel()

                            break

                    # Output audio
                    async with (
                        await create_process(rhasspy, SND_DOMAIN, snd_program)
                    ) as snd_proc:
                        assert snd_proc.stdin is not None
                        assert snd_proc.stdout is not None

                        for remote_event in snd_buffer:
                            if AudioChunk.is_type(remote_event.type):
                                await async_write_event(remote_event, snd_proc.stdin)
                            elif AudioStop.is_type(remote_event.type):
                                # Unexpected, but it could happen
                                continue

                        while True:
                            remote_event = await async_read_event(remote_proc.stdout)
                            if remote_event is None:
                                break

                            if AudioChunk.is_type(remote_event.type):
                                await async_write_event(remote_event, snd_proc.stdin)
                            elif AudioStop.is_type(remote_event.type):
                                await async_write_event(remote_event, snd_proc.stdin)
                                break

                        # Wait for audio to finish playing
                        while True:
                            snd_event = await async_read_event(snd_proc.stdout)
                            if snd_event is None:
                                break

                            if Played.is_type(snd_event.type):
                                break
                except Exception:
                    _LOGGER.exception(
                        "Unexpected error communicating with remote base station"
                    )

        if not args.loop:
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
