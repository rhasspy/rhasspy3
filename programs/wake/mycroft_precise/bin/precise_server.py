#!/usr/bin/env python3
import argparse
import logging
import os
import socket
from pathlib import Path

from precise_runner import PreciseEngine, PreciseRunner, ReadWriteStream

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.event import read_event, write_event
from rhasspy3.wake import Detection, NotDetected

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Location to .pb model file to use (with .pb.params)")
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
    )
    parser.add_argument("--engine", default='.venv/bin/precise-engine', help="Path to precise-engine executable")
    parser.add_argument("--chunk_size", type=int, default=2048, help="Number of *bytes* per prediction. Higher numbers decrease CPU usage but increase latency")
    parser.add_argument("--trigger_level", type=int, default=3, help="Number of chunk activations needed to trigger detection event. Higher values add latency but reduce false positives")
    parser.add_argument("--sensitivity", type=float, default=0.5, help="From 0.0 to 1.0, how sensitive the network should be")
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Need to unlink socket if it exists
    try:
        os.unlink(args.socketfile)
    except OSError:
        pass

    try:
        # Create socket server
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(args.socketfile)
        sock.listen()

        # Load converted faster-whisper model
        engine = PreciseEngine(args.engine, args.model, args.chunk_size)
        stream = ReadWriteStream()

        conn_file_s = None
        is_detected = False
        timestamp = None
        name = os.path.basename(args.model).removesuffix(".pb")
        sensitivity = args.sensitivity

        def activation():
            nonlocal is_detected, timestamp, conn_file_s, name

            _LOGGER.info("Detected")

            if is_detected:
                return
            if conn_file_s is None:
                return

            try:
                write_event(
                    Detection(
                        name=name, timestamp=timestamp
                    ).event(),
                    conn_file_s,
                )  # type: ignore

                is_detected = True
            except Exception:
                pass

        def prediction(prob):
            nonlocal is_detected, conn_file_s

            if not is_detected:
                return
            if conn_file_s is None:
                return
            if prob >= sensitivity:
                return

            try:
                write_event(NotDetected().event(), conn_file_s)  # type: ignore
            except Exception:
                pass

            is_detected = False

        runner = PreciseRunner(engine, trigger_level=args.trigger_level, sensitivity=args.sensitivity, stream=stream, on_activation=activation, on_prediction=prediction)
        runner.start()
        _LOGGER.info("Ready")

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)

                with connection, connection.makefile(mode="rwb") as conn_file:
                    conn_file_s = conn_file
                    while True:
                        event = read_event(conn_file)  # type: ignore
                        if event is None:
                            break

                        if AudioStart.is_type(event.type):
                            _LOGGER.debug("Receiving audio")
                            continue

                        if AudioStop.is_type(event.type):
                            _LOGGER.debug("Audio stopped")
                            break

                        if not AudioChunk.is_type(event.type):
                            continue

                        chunk = AudioChunk.from_event(event)

                        timestamp = chunk.timestamp
                        stream.write(chunk.audio)

                    if is_detected:
                        write_event(NotDetected().event(), conn_file)  # type: ignore

            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
            finally:
                conn_file_s = None
                is_detected = False
    finally:
        os.unlink(args.socketfile)
        runner.stop()


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
