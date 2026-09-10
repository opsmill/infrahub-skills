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
        f'''
def geom(d):
    return {{"width": 220, "svg": {SVG}}}

class T:
    async def transform(self, data: dict) -> str:
        return str(geom(data))
''',
        id="str-of-a-helper-dict",
    ),
    pytest.param(
        '''
class T:
    async def transform(self, data: dict) -> str:
        return str({"width": 220, "height": 900})
''',
        id="str-of-a-dict-literal",
    ),
    pytest.param(
        '''
class T:
    async def transform(self, data: dict) -> str:
        return str(data)
''',
        id="str-of-the-dict-annotated-input",
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
    pytest.param(
        '''
import xml.etree.ElementTree as ET

class T:
    def transform(self, data):
        root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg"})
        return ET.tostring(root, encoding="unicode")
''',
        id="elementtree-tostring-as-unicode",
    ),
    pytest.param(
        f'''
from jinja2 import Template

TPL = Template({SVG})

class T:
    def transform(self, data):
        return TPL.render(width=220)
''',
        id="jinja2-template-render",
    ),
    pytest.param(
        f'''
import textwrap

SVG = {SVG}

class T:
    def transform(self, data):
        return textwrap.dedent(SVG)
''',
        id="textwrap-dedent",
    ),
    pytest.param(
        f'''
import io

class T:
    def transform(self, data):
        buf = io.StringIO()
        buf.write({SVG})
        return buf.getvalue()
''',
        id="stringio-getvalue",
    ),
]


@pytest.mark.parametrize("src", STRING_RETURNS)
def test_a_string_return_passes_with_or_without_the_annotation(src):
    """rules/artifacts-definitions.md requires a string, not an annotation."""
    ok, msg = _returns_str(src)
    assert ok, msg


def test_tostring_without_unicode_encoding_returns_bytes():
    """`ET.tostring(root)` hands back bytes, which serialise to `b'<svg...'`."""
    ok, msg = _returns_str(
        '''
import xml.etree.ElementTree as ET

class T:
    def transform(self, data) -> str:
        return ET.tostring(ET.Element("svg"))
'''
    )
    assert not ok, msg


def test_a_local_helper_outranks_the_string_allowlist():
    """A file-defined `render` is classified by what it returns."""
    ok, msg = _returns_str(
        '''
def render(data):
    return {"width": 220}

class T:
    def transform(self, data):
        return render(data)
'''
    )
    assert not ok, msg


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


def test_an_elementtree_root_counts_as_markup():
    """`ET.Element("svg", ...)` builds the document without the literal."""
    ok, msg = _markup(
        '''
import xml.etree.ElementTree as ET

class T:
    def transform(self, data):
        root = ET.Element("svg", {"xmlns": "http://www.w3.org/2000/svg"})
        return ET.tostring(root, encoding="unicode")
'''
    )
    assert ok, msg


def test_an_elementtree_root_without_the_namespace_still_fails():
    ok, msg = _markup(
        '''
import xml.etree.ElementTree as ET

class T:
    def transform(self, data):
        return ET.tostring(ET.Element("svg"), encoding="unicode")
'''
    )
    assert not ok and "namespace" in msg


def test_an_unreferenced_module_constant_is_not_markup_in_the_output():
    """Markup nothing reaches is not markup the artifact carries."""
    ok, msg = _markup(
        f'''
UNUSED = {SVG}

class T:
    async def transform(self, data: dict) -> str:
        return str({{"width": 220, "height": 900}})
'''
    )
    assert not ok, msg


def test_a_referenced_module_constant_still_counts():
    ok, msg = _markup(
        f'''
TEMPLATE = {SVG}

class T:
    def transform(self, data):
        return TEMPLATE.replace("x", "y")
'''
    )
    assert ok, msg


def test_a_class_attribute_reached_through_self_still_counts():
    ok, msg = _markup(
        f'''
class T:
    TEMPLATE = {SVG}

    def transform(self, data):
        return self.TEMPLATE
'''
    )
    assert ok, msg


def _content_type(md: str):
    return _mod.check_artifact_content_type_declared(md_text=md)


def test_a_prose_mention_before_the_registration_does_not_decide_the_check():
    """Answers that explain the choice first were failed by first-match."""
    ok, msg = _content_type(
        """Do not use `content_type: text/plain` here -- the artifact IS a
diagram, so it needs the vector type:

```yaml
artifact_definitions:
  - name: rack_elevation
    content_type: image/svg+xml
```
"""
    )
    assert ok, msg


def test_a_registration_with_the_wrong_content_type_still_fails():
    ok, msg = _content_type(
        """```yaml
artifact_definitions:
  - name: rack_elevation
    content_type: text/plain
```
"""
    )
    assert not ok and "text/plain" in msg
