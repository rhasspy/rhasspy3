#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path

from precise_runner import PreciseEngine, PreciseRunner, ReadWriteStream

from rhasspy3.audio import AudioChunk, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.wake import Detection, NotDetected

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)

# -----------------------------------------------------------------------------


def main() -> None:
    """Main method."""
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Location to .pb model file to use (with .pb.params)")
    parser.add_argument("--engine", default='.venv/bin/precise-engine', help="Path to precise-engine executable")
    parser.add_argument("--chunk_size", type=int, default=2048, help="Number of *bytes* per prediction. Higher numbers decrease CPU usage but increase latency")
    parser.add_argument("--trigger_level", type=int, default=3, help="Number of chunk activations needed to trigger detection event. Higher values add latency but reduce false positives")
    parser.add_argument("--sensitivity", type=float, default=0.5, help="From 0.0 to 1.0, how sensitive the network should be")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    engine = PreciseEngine(args.engine, args.model, args.chunk_size)
    stream = ReadWriteStream()

    is_detected = False
    timestamp = None
    name = os.path.basename(args.model).removesuffix(".pb")

    def activation():
        nonlocal is_detected, timestamp, name
        try:
            write_event(
                Detection(
                    name=name, timestamp=timestamp
                ).event()
            )
            is_detected = True
        except Exception:
            pass
        

    runner = PreciseRunner(engine, trigger_level=args.trigger_level, sensitivity=args.sensitivity, stream=stream, on_activation=activation)
    runner.start()

    try:
        while True:
            event = read_event()
            if event is None:
                break

            if AudioStop.is_type(event.type):
                break

            if not AudioChunk.is_type(event.type):
                continue

            chunk = AudioChunk.from_event(event)

            timestamp = chunk.timestamp
            stream.write(chunk.audio)

        if is_detected:
            write_event(NotDetected().event())
    except KeyboardInterrupt:
        pass

    runner.stop()

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
