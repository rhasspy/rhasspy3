#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import torch

from rhasspy3.audio import AudioStart, DEFAULT_SAMPLES_PER_CHUNK, AudioChunk, AudioStop
from rhasspy3.event import write_event, read_event
from rhasspy3.tts import Synthesize

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, help="Language to use")
    parser.add_argument("--model", required=True, help="Model to use")
    parser.add_argument("--sample_rate", help="Sample rate", default=48000)
    parser.add_argument("--speaker", help="Voice to use", default='random')
    parser.add_argument("--put_accent", help="Add accent", default=True)
    parser.add_argument("--put_yo", help="Put Yo", default=True)
    parser.add_argument("--samples-per-chunk", type=int, default=DEFAULT_SAMPLES_PER_CHUNK)
    parser.add_argument("--debug", action="store_true", help="Log DEBUG messages")
    parser.add_argument("--destination", help="Path to destination directory")
    parser.add_argument("--voice", help="Saved voice model")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    sys_stdout = sys.stdout
    sys.stdout = StreamToLogger(_LOGGER, logging.INFO)

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
    # Listen for events
    try:
        while True:
            event = read_event()
            if event is None:
                break

            if Synthesize.is_type(event.type):
                synthesize = Synthesize.from_event(event)
                _LOGGER.debug("synthesize: text='%s'", synthesize.text)

                audio = model.apply_tts(text=synthesize.text, **model_params)

                width = 2
                channels = 1
                timestamp = 0
                rate = args.sample_rate
                bytes_per_chunk = args.samples_per_chunk * width

                start_event = AudioStart(rate, width, channels, timestamp=timestamp)
                write_event(start_event.event(), sys_stdout.buffer)
                _LOGGER.debug(start_event)

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
                    write_event(chunk.event(), sys_stdout.buffer)
                    timestamp += chunk.milliseconds
                    audio_bytes = audio_bytes[bytes_per_chunk:]

                write_event(AudioStop(timestamp=timestamp).event(), sys_stdout.buffer)

    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
