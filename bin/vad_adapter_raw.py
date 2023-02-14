#!/usr/bin/env python3
"""Voice activity detection programs that accept raw PCM audio and print a speech probability for each chunk."""
import argparse
import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import Optional

from rhasspy3.audio import AudioChunk, AudioChunkConverter, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.vad import Segmenter, VoiceStarted, VoiceStopped

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    #
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
    parser.add_argument(
        "--samples-per-chunk",
        required=True,
        type=int,
        help="Samples to send to command at a time",
    )
    #
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Speech probability threshold (0-1)",
    )
    parser.add_argument(
        "--speech-seconds",
        type=float,
        default=0.3,
    )
    parser.add_argument(
        "--silence-seconds",
        type=float,
        default=0.5,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--reset-seconds",
        type=float,
        default=1,
    )
    #
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    bytes_per_chunk = args.samples_per_chunk * args.width * args.channels
    seconds_per_chunk = args.samples_per_chunk / args.rate

    command = shlex.split(args.command)
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        assert proc.stdin is not None
        assert proc.stdout is not None

        segmenter = Segmenter(
            args.speech_seconds,
            args.silence_seconds,
            args.timeout_seconds,
            args.reset_seconds,
        )
        converter = AudioChunkConverter(args.rate, args.width, args.channels)
        audio_bytes = bytes()
        is_first_audio = True
        sent_started = False
        sent_stopped = False
        last_stop_timestamp: Optional[int] = None

        while True:
            event = read_event()
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                if is_first_audio:
                    _LOGGER.debug("Receiving audio")
                    is_first_audio = False

                chunk = AudioChunk.from_event(event)
                chunk = converter.convert(chunk)
                audio_bytes += chunk.audio
                timestamp = (
                    time.monotonic_ns() if chunk.timestamp is None else chunk.timestamp
                )
                last_stop_timestamp = timestamp + chunk.milliseconds

                # Handle uneven chunk sizes
                while len(audio_bytes) >= bytes_per_chunk:
                    chunk_bytes = audio_bytes[:bytes_per_chunk]
                    proc.stdin.write(chunk_bytes)
                    proc.stdin.flush()

                    line = proc.stdout.readline().decode()
                    if line:
                        speech_probability = float(line)
                        is_speech = speech_probability > args.threshold
                        segmenter.process(
                            chunk=chunk_bytes,
                            chunk_seconds=seconds_per_chunk,
                            is_speech=is_speech,
                            timestamp=timestamp,
                        )

                        if (not sent_started) and segmenter.started:
                            _LOGGER.debug("Voice started")
                            write_event(
                                VoiceStarted(
                                    timestamp=segmenter.start_timestamp
                                ).event()
                            )
                            sent_started = True

                        if (not sent_stopped) and segmenter.stopped:
                            if segmenter.timeout:
                                _LOGGER.info("Voice timeout")
                            else:
                                _LOGGER.debug("Voice stopped")

                            write_event(
                                VoiceStopped(timestamp=segmenter.stop_timestamp).event()
                            )
                            sent_stopped = True

                    audio_bytes = audio_bytes[bytes_per_chunk:]

            elif AudioStop.is_type(event.type):
                _LOGGER.debug("Audio stopped")
                if not sent_stopped:
                    write_event(VoiceStopped(timestamp=last_stop_timestamp).event())
                    sent_stopped = True

                proc.stdin.close()
                break


if __name__ == "__main__":
    main()
