#!/usr/bin/env python3
import argparse
import logging
import json
import shlex
import subprocess

from rhasspy3.intent import Intent
from rhasspy3.handle import Handled, NotHandled
from rhasspy3.event import write_event, read_event

_LOGGER = logging.getLogger("handle_adapter_text")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        help="Command to run",
    )
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)

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
    try:
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
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
