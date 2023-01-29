#!/usr/bin/env python3
import argparse
import shlex
import subprocess
import sys
import wave

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.asr import Transcript
from rhasspy3.event import read_event, write_event


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("wav", nargs="+", help="WAV file(s) to transcribe")
    parser.add_argument("-s", "--samples-per-chunk", type=int, default=1024)
    args = parser.parse_args()

    command = shlex.split(args.command)

    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE
    ) as proc:
        for wav_path in args.wav:
            with wave.open(wav_path, "rb") as wav_file:
                write_event(AudioStart(timestamp=0).event(), proc.stdin)
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                timestamp = 0
                chunk = wav_file.readframes(args.samples_per_chunk)
                while chunk:
                    chunk_samples = len(chunk) / (width * channels)
                    timestamp += 1000 * (chunk_samples / rate)

                    write_event(
                        AudioChunk(
                            rate=rate, width=width, channels=channels, audio=chunk
                        ).event(),
                        proc.stdin,
                    )
                    chunk = wav_file.readframes(args.samples_per_chunk)

                write_event(AudioStop(timestamp=timestamp).event(), proc.stdin)

                event = read_event(proc.stdout)
                while (event is not None) and (not Transcript.is_type(event.type)):
                    event = read_event(proc.stdout)

                if event is not None:
                    write_event(event, sys.stdout.buffer)


if __name__ == "__main__":
    main()
