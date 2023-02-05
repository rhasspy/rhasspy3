#!/usr/bin/env python3
import re
import sys
from datetime import datetime


def main() -> None:
    text = sys.stdin.read().strip().lower()
    words = [re.sub(r"\W", "", word) for word in text.split()]

    now = datetime.now()
    if "time" in words:
        print(now.strftime("%I:%M %p"))
    elif "date" in words:
        print(now.strftime("%A, %B %d, %Y"))


if __name__ == "__main__":
    main()
