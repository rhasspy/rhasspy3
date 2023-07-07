"""JAML is JSON objects as a *severely* restricted subset of YAML."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
    IN_LIST = auto()
    LITERAL = auto()


@dataclass
class Placeholder:
    key: str
    target: Dict[str, Any]


class JamlLoader:
    def __init__(self) -> None:
        self.output: Dict[str, Any] = {}
        self.indent = 0
        self.state = LoaderState.IN_DICT
        self.literal = ""
        self.target_stack: List[Union[Dict[str, Any], List[Any], str, Placeholder]] = [
            self.output
        ]

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
                if isinstance(target, Placeholder):
                    # Replace with dict
                    target_dict = {}
                    target.target[target.key] = target_dict
                    target = target_dict
                    self.target_stack[-1] = target

                assert isinstance(target, Mapping)
                target[key] = self.literal.strip()

                # Reset indent and state
                self.indent -= _INDENT
                self.state = LoaderState.IN_DICT
            else:
                # Add to literal
                self.literal += "\n" + line.strip()

        if (self.state == LoaderState.IN_LIST) and (line_indent < self.indent):
            # Done with list
            assert len(self.target_stack) > 1
            target_list = self.target_stack.pop()
            assert isinstance(target_list, Sequence), target_list

            # Reset indent and state
            self.indent -= _INDENT
            self.state = LoaderState.IN_DICT

        if self.state == LoaderState.IN_DICT:
            if line_stripped.startswith("-"):
                # Replace with list
                assert len(self.target_stack) > 1
                placeholder = self.target_stack.pop()
                assert isinstance(placeholder, Placeholder)
                target_list = []
                placeholder.target[placeholder.key] = target_list
                self.target_stack.append(target_list)

                self.indent = line_indent
                self.state = LoaderState.IN_LIST
            else:
                self._add_key(line, line_indent)

        if self.state == LoaderState.IN_LIST:
            self._add_list_item(line, line_indent)

    def _add_key(self, line, line_indent: int):
        while line_indent < self.indent:
            self.target_stack.pop()
            self.indent -= _INDENT

        assert self.target_stack
        target = self.target_stack[-1]
        if isinstance(target, Placeholder):
            # Replace with dict
            target_dict = {}
            target.target[target.key] = target_dict
            target = target_dict
            self.target_stack[-1] = target

        assert isinstance(target, Mapping), target

        parts = line.split(":", maxsplit=1)
        assert len(parts) == 2, f"Invalid key/value pair: {line}"
        key = parts[0].strip()
        value = parts[1].strip()

        assert not key.startswith("-"), "Lists are not supported"

        # Remove inline comments
        if value and (value[0] in ("'", '"')):
            # Just keep what's in quotes.
            # This doesn't take escapes, etc. into account.
            end_quote = value.find(value[0], 1)
            value = value[: end_quote + 1]
        else:
            # Remove comment
            value = value.split("#", maxsplit=1)[0]

        value_is_dict = True

        if value:
            value_is_dict = False

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

        if value_is_dict:
            self.target_stack.append(Placeholder(key, target))
            self.indent += _INDENT
        else:
            target[key] = value

    def _add_list_item(self, line, line_indent: int):
        assert self.target_stack
        target = self.target_stack[-1]
        assert isinstance(target, Sequence), target

        line_stripped = line.strip()
        assert len(line_stripped) > 1
        assert line_stripped[0] == "-", line_stripped

        # Remove "-"
        value = line_stripped[1:].strip()

        if value[0] in ("'", '"'):
            # Remove quotes
            value = value[1:-1]
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

        target.append(value)
