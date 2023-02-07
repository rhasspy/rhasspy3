"""JAML is JSON as a severely restructed subset of YAML."""
from collections.abc import Mapping, Sequence
from enum import auto, Enum
from typing import Any, Dict, List, IO, Union, Optional

_INDENT = 2


def safe_load(fp: IO[str]) -> Dict[str, Any]:
    loader = JamlLoader()
    for line in fp:
        loader.process_line(line)

    return loader.output


class LoaderState:
    KEY_OR_ITEM = auto()
    IN_DICT = auto()
    IN_LIST = auto()
    BLOCKQUOTE = auto()


class JamlLoader:
    def __init__(self) -> None:
        self.output: Dict[str, Any] = {}
        self.indent = 0
        # self.state = LoaderState.KEY_OR_ITEM
        self.key: Optional[str] = None
        self.literal: Optional[str] = None

        # indent -> dict or list
        # TODO: Make stack?
        self.targets: Dict[int, Dict[str, Any]] = {0: self.output}

    def process_line(self, line: str):
        line_stripped = line.strip()
        if line_stripped.startswith("#"):
            # Comment
            return

        if not line_stripped:
            # Empty line
            target = self.targets.pop(self.indent + _INDENT, None)
            if self.literal is not None:
                assert self.key is not None
                assert target is not None
                target[self.key] = self.literal
                self.literal = None

            self.indent = 0
            return

        if self.literal is not None:
            line_indent = len(line_stripped) - len(line.lstrip())
            if line_indent < self.indent:
                target = self.targets.get(self.indent + _INDENT, None)

        # Remove inline comments
        original_line = line
        line = line.split("#", maxsplit=1)[0]
        line = line.rstrip()

        line_lstripped = line.lstrip()
        line_indent = len(line) - len(line_lstripped)
        assert (line_indent % _INDENT) == 0, f"Bad indent: {original_line}"

        # if line_indent > self.indent:
        #     target = self.targets.get(self.indent)
        #     assert target is not None

        #     self.indent = line_indent
        # elif line_indent < self.indent:
        #     # Target is complete
        #     self.targets.pop(self.indent, None)
        #     self.indent = line_indent
        #     target = self.targets.get(self.indent)
        # else:
        #     # Same indent as last line
        #     # self.targets.pop(self.indent, None)
        #     # self.indent = line_indent
        #     pass

        is_item = line_lstripped.startswith("-")
        if is_item:
            self.key = None
            value: Any = line_lstripped[1:].lstrip()
        else:
            parts = line.split(":", maxsplit=1)
            self.key = parts[0].strip()
            value = parts[1].strip()

            if value:
                if value[0] in ("'", '"'):
                    # Remove quotes
                    value = value[1:-1]
                elif value == "|":
                    self.literal = ""
                    self.indent += _INDENT
                elif value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                else:
                    try:
                        value = int(value)
                    except ValueError:
                        try:
                            value = float(value)
                        except ValueError:
                            pass

        if self.key:
            target = self.targets.get(self.indent)
            assert target is not None, f"No target at indent {self.indent}"
            assert isinstance(target, Mapping)

            if value:
                target[self.key] = value
            else:
                new_target: Dict[str, Any] = {}
                target[self.key] = new_target
                self.targets[self.indent + _INDENT] = new_target
                self.indent += _INDENT

        # if is_key:

        # if self.state == LoaderState.IN_DICT_OR_LIST:
