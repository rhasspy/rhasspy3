#!/usr/bin/env python3
import argparse
import json
import logging
import sys

from vosk import Model, KaldiRecognizer, SetLogLevel

from rhasspy3.audio import AudioChunk, AudioStart, AudioStop
from rhasspy3.asr import Transcript
from rhasspy3.event import read_event, write_event

_LOGGER = logging.getLogger("vosk_stream")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="Path to Vosk model directory")
    parser.add_argument(
        "-r",
        "--rate",
        type=int,
        default=16000,
        help="Input audio sample rate (default: 16000)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

    SetLogLevel(0)

    model = Model(args.model)
    recognizer = KaldiRecognizer(
        model,
        args.rate,
    )
    is_first_audio = True

    try:
        while True:
            event = read_event(sys.stdin.buffer)
            if event is None:
                break

            if AudioChunk.is_type(event.type):
                if is_first_audio:
                    _LOGGER.info("Receiving audio")
                    is_first_audio = False

                chunk = AudioChunk.from_event(event)
                recognizer.AcceptWaveform(chunk.audio)
            elif AudioStart.is_type(event.type):
                _LOGGER.info("Start")
                is_first_audio = True
                recognizer = KaldiRecognizer(
                    model,
                    args.rate,
                )
            elif AudioStop.is_type(event.type):
                _LOGGER.info("Stop")

                result = json.loads(recognizer.FinalResult())
                _LOGGER.info(result)
                text = result["text"]

                write_event(Transcript(text=text).event(), sys.stdout.buffer)
                is_first_audio = True
    except KeyboardInterrupt:
        pass


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
