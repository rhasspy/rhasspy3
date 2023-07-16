from dataclasses import dataclass
from typing import Dict, List, Optional

from rhasspy3.util.dataclasses_json import DataClassJsonMixin


@dataclass
class Class1(DataClassJsonMixin):
    name: str


@dataclass
class Class1_V2(DataClassJsonMixin):
    name: str
    description: Optional[str]


@dataclass
class Class2(DataClassJsonMixin):
    name: str
    obj1: Class1
    list1: List[Class1]
    dict1: Dict[str, Class1]
    opt1: Optional[Class1]


@dataclass
class Class2_V2(DataClassJsonMixin):
    name: str
    obj1: Class1_V2
    list1: List[Class1_V2]
    dict1: Dict[str, Class1_V2]
    opt1: Optional[Class1_V2]


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

_DICT_V2 = {
    "name": "2",
    "obj1": {"name": "1", "description": "desc1"},
    "list1": [{"name": "1-2", "description": "desc2"}],
    "dict1": {"key": {"name": "1-3", "description": "desc3"}},
    "opt1": {"name": "1-4", "description": "desc4"},
}
_OBJ_V2 = Class2_V2(
    name="2",
    obj1=Class1_V2(name="1", description="desc1"),
    list1=[Class1_V2(name="1-2", description="desc2")],
    dict1={"key": Class1_V2(name="1-3", description="desc3")},
    opt1=Class1_V2(name="1-4", description="desc4"),
)
_OBJ_V2_1 = Class2_V2(
    name="2",
    obj1=Class1_V2(name="1", description=None),
    list1=[Class1_V2(name="1-2", description=None)],
    dict1={"key": Class1_V2(name="1-3", description=None)},
    opt1=Class1_V2(name="1-4", description=None),
)


def test_to_dict():
    assert _OBJ.to_dict() == _DICT


def test_from_dict():
    assert Class2.from_dict(_DICT) == _OBJ


def test_from_dict_v2():
    # Original class works with new fields
    assert Class2.from_dict(_DICT_V2) == _OBJ

    # New class has optional fields set to None
    assert Class2_V2.from_dict(_DICT) == _OBJ_V2_1

    # New class can decide new fields
    assert Class2_V2.from_dict(_DICT_V2) == _OBJ_V2


def test_extra_field():
    # Extra fields are ignored
    assert Class2.from_dict({"extra_field": "not defined in class", **_DICT}) == _OBJ
