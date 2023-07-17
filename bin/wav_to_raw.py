#!/usr/bin/env python3
import argparse
import audioop
import sys
import wave


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples-per-chunk",
        type=int,
        default=1024,
        help="Number of samples to read at a time",
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
        choices=(1, 2),
        help="Sample channel count",
    )
    args = parser.parse_args()
    bytes_per_chunk = args.samples_per_chunk * args.width * args.channels

    with wave.open(sys.stdin.buffer, "rb") as wav_file:
        rate = wav_file.getframerate()
        width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        samples = wav_file.readframes(args.samples_per_chunk)

        while samples:
            if len(samples) < bytes_per_chunk:
                # Pad last sample
                samples += bytes(bytes_per_chunk - len(samples))

            if width != args.width:
                # Convert sample width
                samples = audioop.lin2lin(samples, width, args.width)
                width = args.width

            if channels != args.channels:
                # Convert to mono or stereo
                if args.channels == 1:
                    samples = audioop.tomono(samples, width, 1.0, 1.0)
                elif args.channels == 2:
                    samples = audioop.tostereo(samples, width, 1.0, 1.0)
                else:
                    raise ValueError(f"Cannot convert to channels: {args.channels}")

                channels = args.channels

            if rate != args.rate:
                # Resample
                samples, _state = audioop.ratecv(
                    samples,
                    width,
                    channels,
                    rate,
                    args.rate,
                    None,
                )
                rate = args.rate

            sys.stdout.buffer.write(samples)

            # Next chunk
            samples = wav_file.readframes(args.samples_per_chunk)


if __name__ == "__main__":
    main()
