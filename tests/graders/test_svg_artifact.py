"""Tests for the SVG-artifact checks in graders/managing-transforms/lib.py.

The combination that motivated these: a transform annotated `-> str` whose
dict comes from a helper and whose SVG markup sits in a docstring. That is
exactly the silent failure the rule exists to prevent, and it scored 1.00.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "managing_transforms_lib", _REPO_ROOT / "graders" / "managing-transforms" / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

SVG = "'<svg xmlns=\"http://www.w3.org/2000/svg\">x</svg>'"


def _returns_str(src: str):
    return _mod.check_svg_transform_returns_str(tree=ast.parse(src), py_raw=src)


def _markup(src: str):
    return _mod.check_svg_markup_in_output(tree=ast.parse(src), py_raw=src)


DICT_RETURNS = [
    pytest.param(
        f'''
def geom(data):
    return {{"width": 220, "height": 900}}

class T:
    async def transform(self, data: dict) -> str:
        """Renders {SVG[1:-1]} for a rack."""
        return geom(data)
''',
        id="helper-dict-annotated-str-markup-in-docstring",
    ),
    pytest.param(
        '''
class T:
    async def transform(self, data: dict) -> str:
        return {"width": 220}
''',
        id="dict-literal",
    ),
    pytest.param(
        '''
def geom(d):
    return dict(a=1)

class T:
    async def transform(self, data: dict) -> str:
        return geom(data).copy()
''',
        id="copy-of-a-helper-dict",
    ),
    pytest.param(
        '''
def geom(d):
    out = {}
    out["a"] = 1
    return out

class T:
    async def transform(self, data: dict) -> str:
        g = geom(data)
        return g
''',
        id="two-hop-through-a-helper",
    ),
]


@pytest.mark.parametrize("src", DICT_RETURNS)
def test_a_dict_return_fails_however_it_is_reached(src):
    ok, msg = _returns_str(src)
    assert not ok, msg


def test_an_annotation_alone_is_not_evidence():
    """Python does not enforce `-> str`, so it is a claim about the return."""
    ok, msg = _returns_str(
        '''
import copy

def geom(d):
    return {"a": 1}

class T:
    async def transform(self, data: dict) -> str:
        return copy.deepcopy(geom(data))
'''
    )
    assert not ok and "not evidence" in msg


STRING_RETURNS = [
    pytest.param(
        f'''
class T:
    async def transform(self, data: dict) -> str:
        return f{SVG}
''',
        id="inline-f-string-annotated",
    ),
    pytest.param(
        f'''
def render(data):
    return f{SVG}

class T:
    def transform(self, data):
        return render(data)
''',
        id="helper-string-no-annotation",
    ),
]


@pytest.mark.parametrize("src", STRING_RETURNS)
def test_a_string_return_passes_with_or_without_the_annotation(src):
    """rules/artifacts-definitions.md requires a string, not an annotation."""
    ok, msg = _returns_str(src)
    assert ok, msg


def test_markup_in_a_docstring_is_not_markup_in_the_output():
    ok, msg = _markup(
        f'''
class T:
    async def transform(self, data: dict) -> str:
        """Renders {SVG[1:-1]} for a rack."""
        return str(data)
'''
    )
    assert not ok, msg


def test_markup_built_in_a_helper_still_counts():
    ok, msg = _markup(
        f'''
def render(data):
    return f{SVG}

class T:
    def transform(self, data):
        return render(data)
'''
    )
    assert ok, msg
