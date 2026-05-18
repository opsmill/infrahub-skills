"""Tests for graders/managing-generators/lib.py AST helpers."""

import importlib.util
from pathlib import Path

import pytest

# Load the hyphenated-directory module by file path
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "managing-generators" / "lib.py"
_spec = importlib.util.spec_from_file_location(
    "managing_generators_graders_lib", _LIB_PATH
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

find_client_create_calls = _mod.find_client_create_calls
find_client_get_calls = _mod.find_client_get_calls
find_relationship_add_calls = _mod.find_relationship_add_calls
get_data_dict_items = _mod.get_data_dict_items
is_hfid_dict = _mod.is_hfid_dict
is_id_dict = _mod.is_id_dict
is_bare_string = _mod.is_bare_string
is_name_or_attribute = _mod.is_name_or_attribute
load_output_py = _mod.load_output_py


import ast


def _parse(src: str) -> ast.Module:
    return ast.parse(src)


def test_find_client_create_calls_finds_await_self_client_create():
    tree = _parse(
        "async def f():\n"
        "    await self.client.create(kind='D', data={'name': 'x'})\n"
    )
    calls = find_client_create_calls(tree)
    assert len(calls) == 1


def test_find_client_create_calls_ignores_other_create_calls():
    tree = _parse(
        "async def f():\n"
        "    await some.other.create(kind='D')\n"
        "    await self.client.update(kind='D')\n"
    )
    assert find_client_create_calls(tree) == []


def test_get_data_dict_items_returns_literal_dict_entries():
    tree = _parse(
        "x = self.client.create(kind='D', data={'name': 'x', 'status': 'active'})\n"
    )
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    items = get_data_dict_items(calls[0])
    assert set(items.keys()) == {"name", "status"}


def test_is_hfid_dict_matches_hfid_list_literal():
    node = ast.parse("x = {'hfid': ['cEdge-1000']}").body[0].value
    ok, elts = is_hfid_dict(node)
    assert ok is True
    assert len(elts) == 1
    assert isinstance(elts[0], ast.Constant)
    assert elts[0].value == "cEdge-1000"


def test_is_hfid_dict_rejects_non_dict_or_wrong_key():
    assert is_hfid_dict(ast.parse("x = 'foo'").body[0].value) == (False, None)
    assert is_hfid_dict(ast.parse("x = {'id': '...'}").body[0].value) == (False, None)


def test_is_id_dict_matches_id_dict_literal():
    assert is_id_dict(ast.parse("x = {'id': 'abc'}").body[0].value) is True
    assert is_id_dict(ast.parse("x = {'hfid': ['a']}").body[0].value) is False


def test_is_bare_string_matches_only_string_constants():
    assert is_bare_string(ast.parse("x = 'hi'").body[0].value) is True
    assert is_bare_string(ast.parse("x = 42").body[0].value) is False
    assert is_bare_string(ast.parse("x = ['a']").body[0].value) is False


def test_is_name_or_attribute_matches_variable_and_attribute_refs():
    assert is_name_or_attribute(ast.parse("x = device").body[0].value) is True
    assert is_name_or_attribute(ast.parse("x = self.device").body[0].value) is True
    assert is_name_or_attribute(ast.parse("x = 'd'").body[0].value) is False


def test_find_relationship_add_calls_finds_any_add():
    tree = _parse(
        "def f():\n"
        "    group.members.add(device)\n"
        "    other.foo.add([1, 2])\n"
        "    plain.bar()\n"
    )
    assert len(find_relationship_add_calls(tree)) == 2


def test_find_client_get_calls_finds_self_client_get():
    tree = _parse(
        "async def f():\n"
        "    x = await self.client.get(kind='D', name__value='x')\n"
        "    y = await self.client.create(kind='D')\n"
    )
    assert len(find_client_get_calls(tree)) == 1


def test_load_output_py_returns_none_for_missing_file():
    tree, raw = load_output_py(Path("/nonexistent/path.py"))
    assert tree is None
    assert raw == ""


def test_load_output_py_returns_none_tree_on_syntax_error(tmp_path):
    p = tmp_path / "broken.py"
    p.write_text("def f(:\n")
    tree, raw = load_output_py(p)
    assert tree is None
    assert "def f" in raw
