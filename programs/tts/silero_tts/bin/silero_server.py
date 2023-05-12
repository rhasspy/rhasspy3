#!/usr/bin/env python3
import argparse
import json
import logging
import os
import socket
from pathlib import Path

import numpy as np
import torch

from rhasspy3.audio import AudioStart, DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStop
from rhasspy3.event import write_event

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, help="Language to use")
    parser.add_argument("--model", required=True, help="Model to use")
    parser.add_argument("--sample_rate", help="Sample rate", default=48000)
    parser.add_argument("--speaker", help="Voice to use", default='random')
    parser.add_argument("--put_accent", help="Add accent", default=True)
    parser.add_argument("--put_yo", help="Put Yo", default=True)
    parser.add_argument("--socketfile", required=True, help="Path to Unix domain socket file")
    parser.add_argument("--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK)
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--destination", help="Path to destination directory (default: share)")
    parser.add_argument("--voice", help="Saved voice model")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Need to unlink socket if it exists
    try:
        os.unlink(args.socketfile)
    except OSError:
        pass

    try:
        if args.destination:
            data_path = Path(args.destination)
        else:
            data_path = _DIR.parent.parent.parent.parent / "data" / "tts" / "silero_tts"

        model_path = data_path / "models" / args.language / f'{args.model}.pt'

        model_params = {
            'speaker': args.speaker,
            'sample_rate': args.sample_rate,
            'put_accent': args.put_accent,
            'put_yo': args.put_yo
        }

        if args.voice:
            voice_path = Path(args.voice)
            if voice_path.is_absolute():
                model_params['voice_path'] = voice_path
            else:
                model_params['voice_path'] = data_path / 'voices' / voice_path

        device = torch.device('cpu')
        model = torch.package.PackageImporter(model_path).load_pickle("tts_models", "model")
        model.to(device)
        # Create socket server
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(args.socketfile)
        sock.listen()

        # Listen for connections
        while True:
            try:
                connection, client_address = sock.accept()
                _LOGGER.debug("Connection from %s", client_address)
                with connection, connection.makefile(mode="rwb") as conn_file:
                    while True:
                        event_info = json.loads(conn_file.readline())
                        event_type = event_info["type"]

                        if event_type != "synthesize":
                            continue

                        raw_text = event_info["data"]["text"]
                        text = raw_text.strip()

                        _LOGGER.debug("synthesize: raw_text=%s, text='%s'", raw_text, text)

                        audio = model.apply_tts(text=text, **model_params)

                        width = 2
                        channels = 1
                        timestamp = 0
                        rate = args.sample_rate
                        bytes_per_chunk = args.samples_per_chunk * width

                        write_event(AudioStart(rate, width, channels, timestamp=timestamp).event(), conn_file)

                        # Audio
                        audio_bytes = (32767 * audio).numpy().astype(np.int16).tobytes()

                        while audio_bytes:
                            chunk = AudioChunk(
                                rate,
                                width,
                                channels,
                                audio_bytes[:bytes_per_chunk],
                                timestamp=timestamp,
                            )
                            write_event(chunk.event(), conn_file)
                            timestamp += chunk.milliseconds
                            audio_bytes = audio_bytes[bytes_per_chunk:]

                        write_event(AudioStop(timestamp=timestamp).event(), conn_file)
                        break
            except KeyboardInterrupt:
                break
            except Exception:
                _LOGGER.exception("Error communicating with socket client")
    finally:
        os.unlink(args.socketfile)


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
