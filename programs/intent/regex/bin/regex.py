#!/usr/bin/env python3
import argparse
import re
from collections import defaultdict
from typing import Dict, List, Optional

from rhasspy3.event import read_event, write_event
from rhasspy3.intent import Entity, Intent, NotRecognized, Recognize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--intent",
        required=True,
        nargs=2,
        metavar=("name", "regex"),
        action="append",
        default=[],
        help="Intent name and regex",
    )
    args = parser.parse_args()

    # intent name -> [pattern]
    patterns: Dict[str, List[re.Pattern]] = defaultdict(list)

    for intent_name, pattern_str in args.intent:
        patterns[intent_name].append(re.compile(pattern_str, re.IGNORECASE))

    try:
        while True:
            event = read_event()
            if event is None:
                break

            if Recognize.is_type(event.type):
                recognize = Recognize.from_event(event)
                text = _clean(recognize.text)
                intent = _recognize(text, patterns)
                if intent is None:
                    write_event(NotRecognized().event())
                else:
                    write_event(intent.event())
    except KeyboardInterrupt:
        pass


def _clean(text: str) -> str:
    text = " ".join(text.split())
    return text


def _recognize(text: str, patterns: Dict[str, List[re.Pattern]]) -> Optional[Intent]:
    for intent_name, intent_patterns in patterns.items():
        for intent_pattern in intent_patterns:
            match = intent_pattern.match(text)
            if match is None:
                continue

            return Intent(
                name=intent_name,
                entities=[
                    Entity(name=name, value=value)
                    for name, value in match.groupdict().items()
                ],
            )

    return None


if __name__ == "__main__":
    main()
