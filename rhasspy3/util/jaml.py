"""JAML is JSON objects as a *severely* restricted subset of YAML."""
from collections.abc import Mapping
from enum import Enum, auto
from typing import IO, Any, Dict, List, Union

_INDENT = 2


def safe_load(fp: IO[str]) -> Dict[str, Any]:
    loader = JamlLoader()
    for line in fp:
        loader.process_line(line)

    return loader.output


class LoaderState(Enum):
    IN_DICT = auto()
    LITERAL = auto()


class JamlLoader:
    def __init__(self) -> None:
        self.output: Dict[str, Any] = {}
        self.indent = 0
        self.state = LoaderState.IN_DICT
        self.literal = ""
        self.target_stack: List[Union[Dict[str, Any], str]] = [self.output]

    def process_line(self, line: str):
        line_stripped = line.strip()
        if line_stripped.startswith("#") or (not line_stripped):
            # Comment or empty line
            return

        line_indent = len(line) - len(line.lstrip())
        if self.state == LoaderState.LITERAL:
            # Multi-line literal
            if line_indent < self.indent:
                # Done with literal
                assert len(self.target_stack) > 1
                key = self.target_stack.pop()
                assert isinstance(key, str)

                target = self.target_stack[-1]
                assert isinstance(target, Mapping)
                target[key] = self.literal.strip()

                # Reset indent and state
                self.indent -= _INDENT
                self.state = LoaderState.IN_DICT
            else:
                # Add to literal
                self.literal += "\n" + line.strip()

        if self.state == LoaderState.IN_DICT:
            self._add_key(line, line_indent)

    def _add_key(self, line, line_indent: int):
        while line_indent < self.indent:
            self.target_stack.pop()
            self.indent -= _INDENT

        assert self.target_stack
        target = self.target_stack[-1]
        assert isinstance(target, Mapping)

        # Remove inline comments
        line = line.split("#", maxsplit=1)[0]
        line = line.rstrip()

        parts = line.split(":", maxsplit=1)
        assert len(parts) == 2
        key = parts[0].strip()
        value = parts[1].strip()

        assert not key.startswith("-"), "Lists are not supported"

        if value:
            if value[0] in ("'", '"'):
                # Remove quotes
                value = value[1:-1]
            elif value == "|":
                self.literal = ""
                self.target_stack.append(key)
                self.indent += _INDENT
                self.state = LoaderState.LITERAL
                return
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

        if value:
            target[key] = value
        else:
            new_target: Dict[str, Any] = {}
            target[key] = new_target
            self.target_stack.append(new_target)
            self.indent += _INDENT
