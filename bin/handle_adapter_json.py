#!/usr/bin/env python3
import argparse
import json
import logging
import shlex
import subprocess
from pathlib import Path

from rhasspy3.event import read_event, write_event
from rhasspy3.handle import Handled, NotHandled
from rhasspy3.intent import Intent, NotRecognized

_FILE = Path(__file__)
_DIR = _FILE.parent
_LOGGER = logging.getLogger(_FILE.stem)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    parser.add_argument(
        "--debug", action="store_true", help="Print DEBUG messages to console"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    if args.shell:
        command = args.command
    else:
        command = shlex.split(args.command)

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        shell=args.shell,
        universal_newlines=True,
    )
    with proc:
        assert proc.stdin is not None
        assert proc.stdout is not None

        while True:
            event = read_event()
            if event is None:
                break

            if Intent.is_type(event.type):
                intent = Intent.from_event(event)
                stdout, _stderr = proc.communicate(
                    input=json.dumps(
                        {
                            "intent": {
                                "name": intent.name,
                            },
                            "entities": [
                                {"entity": entity.name, "value": entity.value}
                                for entity in intent.entities or []
                            ],
                            "slots": {
                                entity.name: entity.value
                                for entity in intent.entities or []
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                handled = False
                for line in stdout.splitlines():
                    line = line.strip()
                    if line:
                        write_event(Handled(text=line).event())
                        handled = True
                        break

                if not handled:
                    write_event(NotHandled().event())

                break

            if NotRecognized.is_type(event.type):
                write_event(NotHandled().event())
                break


if __name__ == "__main__":
    main()
