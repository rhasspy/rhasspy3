#!/usr/bin/env python3
"""Reads raw audio chunks from stdin."""
import argparse
import asyncio
import logging
import shlex
import time
from pathlib import Path
from typing import Optional

from rhasspy3.audio import DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStart, AudioStop
from rhasspy3.event import async_get_stdin, async_read_event, write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true", help="Run command with shell")
    #
    parser.add_argument("--filter", help="Program to filter raw audio through")
    #
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=DEFAULT_SAMPLES_PER_CHUNK,
        help="Number of samples to read at a time from command",
    )
    parser.add_argument(
        "--rate",
        type=int,
        required=True,
        help="Sample rate (hz)",
    )
    parser.add_argument(
        "--width",
        type=int,
        required=True,
        help="Sample width bytes",
    )
    parser.add_argument(
        "--channels",
        type=int,
        required=True,
        help="Sample channel count",
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * args.width * args.channels

    if args.shell:
        proc = await asyncio.create_subprocess_shell(
            args.command,
            stdout=asyncio.subprocess.PIPE,
        )
    else:
        program, *program_args = shlex.split(args.command)
        proc = await asyncio.create_subprocess_exec(
            program,
            *program_args,
            stdout=asyncio.subprocess.PIPE,
        )

    assert proc.stdout is not None

    # Filter for raw input audio.
    # The program must return the same number of bytes for each chunk.
    filter_proc: "Optional[asyncio.subprocess.Process]" = None
    if args.filter:
        filter_program, *filter_args = shlex.split(args.filter)
        _LOGGER.debug(
            "Running filter: program=%s, args=%s", filter_program, filter_args
        )
        filter_proc = await asyncio.create_subprocess_exec(
            filter_program,
            *filter_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        assert filter_proc.stdin is not None
        assert filter_proc.stdout is not None

        filter_proc.stdin.write(bytes(2048))
        await filter_proc.stdin.drain()
        await filter_proc.stdout.readexactly(2048)

    stdin_reader = await async_get_stdin()
    stdin_task = asyncio.create_task(async_read_event(stdin_reader))
    proc_task = asyncio.create_task(proc.stdout.readexactly(bytes_per_chunk))
    pending = {stdin_task, proc_task}

    write_event(
        AudioStart(
            args.rate, args.width, args.channels, timestamp=time.monotonic_ns()
        ).event()
    )

    try:
        while True:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )

            if stdin_task in done:
                # Event from stdin
                event = stdin_task.result()
                if event is None:
                    break

                if AudioStop.is_type(event.type):
                    break

                # Next stdin event
                stdin_task = asyncio.create_task(async_read_event(stdin_reader))
                pending.add(stdin_task)

            if proc_task in done:
                # Audio chunk from mic process
                audio_bytes = proc_task.result()
                if not audio_bytes:
                    break

                if filter_proc is not None:
                    assert filter_proc.stdin is not None
                    assert filter_proc.stdout is not None

                    filter_proc.stdin.write(audio_bytes)
                    await filter_proc.stdin.drain()
                    audio_bytes = await filter_proc.stdout.readexactly(len(audio_bytes))

                write_event(
                    AudioChunk(
                        args.rate,
                        args.width,
                        args.channels,
                        audio_bytes,
                        timestamp=time.monotonic_ns(),
                    ).event()
                )

                # Next chunk
                proc_task = asyncio.create_task(
                    proc.stdout.readexactly(bytes_per_chunk)
                )
                pending.add(proc_task)
    finally:
        write_event(AudioStop().event())

        for task in pending:
            task.cancel()

        if proc.returncode is None:
            _LOGGER.debug("Stopping %s", args.command)
            proc.terminate()
            await proc.wait()

        if (filter_proc is not None) and (filter_proc.returncode is None):
            # Stop filter
            _LOGGER.debug("Stopping %s", args.filter)
            filter_proc.stdin.close()
            await filter_proc.wait()

    _LOGGER.info("Stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
