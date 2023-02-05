from dataclasses import dataclass
from typing import Dict, List, Optional

from rhasspy3.util.dataclasses_json import DataClassJsonMixin


@dataclass
class Class1(DataClassJsonMixin):
    name: str


@dataclass
class Class2(DataClassJsonMixin):
    name: str
    obj1: Class1
    list1: List[Class1]
    dict1: Dict[str, Class1]
    opt1: Optional[Class1]


_DICT = {
    "name": "2",
    "obj1": {"name": "1"},
    "list1": [{"name": "1-2"}],
    "dict1": {"key": {"name": "1-3"}},
    "opt1": {"name": "1-4"},
}
_OBJ = Class2(
    name="2",
    obj1=Class1(name="1"),
    list1=[Class1(name="1-2")],
    dict1={"key": Class1(name="1-3")},
    opt1=Class1(name="1-4"),
)


def test_to_dict():
    assert _OBJ.to_dict() == _DICT


def test_from_dict():
    assert Class2.from_dict(_DICT) == _OBJ
