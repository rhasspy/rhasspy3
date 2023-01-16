#!/usr/bin/env python3
import argparse
import json
import logging
import os
import socket
import sys
import threading
from pathlib import Path

from stt import Model
import numpy as np

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.asr import Transcript
from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger("coqui_stt_server")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Coqui STT model directory")
    parser.add_argument(
        "--scorer", help="Path to scorer (default: .scorer file in model directory)"
    )
    parser.add_argument(
        "--alpha-beta",
        type=float,
        nargs=2,
        metavar=("alpha", "beta"),
        help="Scorer alpha/beta",
    )
    parser.add_argument(
        "--socketfile", required=True, help="Path to Unix domain socket file"
    )
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=16000,
        help="Input audio sample rate (default: 16000)",
    )
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

        model_dir = Path(args.model)
        model_path = next(model_dir.glob("*.tflite"))
        if args.scorer:
            scorer_path = Path(args.scorer)
        else:
            scorer_path = next(model_dir.glob("*.scorer"))

        _LOGGER.debug("Loading model: %s, scorer: %s", model_path, scorer_path)
        model = Model(str(model_path))
        model.enableExternalScorer(str(scorer_path))

        if args.alpha_beta is not None:
            model.setScorerAlphaBeta(*args.alpha_beta)

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)

                # Start new thread for client
                threading.Thread(
                    target=handle_client,
                    args=(connection, model, args.rate),
                    daemon=True,
                ).start()
            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


def handle_client(connection: socket.socket, model: Model, rate: int) -> None:
    try:
        model_stream = model.createStream()
        is_first_audio = True

        with connection, connection.makefile(mode="rwb") as conn_file:
            while True:
                event = read_event(conn_file)
                if event is None:
                    break

                if AudioChunk.is_type(event.type):
                    if is_first_audio:
                        _LOGGER.debug("Receiving audio")
                        is_first_audio = False

                    chunk = AudioChunk.from_event(event)
                    chunk_array = np.frombuffer(chunk.audio, dtype=np.int16)
                    model_stream.feedAudioContent(chunk_array)
                elif AudioStop.is_type(event.type):
                    _LOGGER.info("Audio stopped")

                    text = model_stream.finishStream()
                    write_event(Transcript(text=text).event(), conn_file)
                    break
    except Exception:
        _LOGGER.exception("Unexpected error in client thread")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
