"""Tests for graders/managing-generators/lib.py AST helpers."""

import importlib.util
from pathlib import Path

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


SRC_GOOD_HFID = """
async def f(self):
    await self.client.create(
        kind="DcimDevice",
        data={
            "name": "cEdge-1",
            "device_type": {"hfid": ["cEdge-1000"]},
            "platform": {"hfid": ["ios-xe"]},
        },
    )
"""

SRC_BARE_STRING = """
async def f(self):
    await self.client.create(
        kind="DcimDevice",
        data={
            "name": "cEdge-1",
            "device_type": "cEdge-1000",
        },
    )
"""

SRC_OVERPACKED_HFID = """
async def f(self):
    await self.client.create(
        kind="DcimDevice",
        data={
            "device_type": {"hfid": ["cEdge-1000", "Cisco"]},
        },
    )
"""


def test_relationship_hfid_form_correct_passes_on_good():
    tree = ast.parse(SRC_GOOD_HFID)
    ok, msg = _mod.CHECKS["relationship-hfid-form-correct"](tree)
    assert ok, msg


def test_relationship_hfid_form_correct_fails_on_bare_string():
    tree = ast.parse(SRC_BARE_STRING)
    ok, msg = _mod.CHECKS["relationship-hfid-form-correct"](tree)
    assert not ok
    assert "device_type" in msg


def test_no_bare_string_relationship_fails_on_bare():
    tree = ast.parse(SRC_BARE_STRING)
    ok, msg = _mod.CHECKS["no-bare-string-relationship"](tree)
    assert not ok


def test_no_bare_string_relationship_passes_on_good():
    tree = ast.parse(SRC_GOOD_HFID)
    ok, msg = _mod.CHECKS["no-bare-string-relationship"](tree)
    assert ok


def test_no_overpacked_hfid_fails_on_overpacked():
    tree = ast.parse(SRC_OVERPACKED_HFID)
    ok, msg = _mod.CHECKS["no-overpacked-hfid-list"](tree)
    assert not ok
    assert "device_type" in msg


def test_no_overpacked_hfid_passes_on_good():
    tree = ast.parse(SRC_GOOD_HFID)
    ok, msg = _mod.CHECKS["no-overpacked-hfid-list"](tree)
    assert ok


SRC_EMPTY_HFID = """
async def f(self):
    await self.client.create(
        kind="DcimDevice",
        data={
            "device_type": {"hfid": []},
        },
    )
"""


def test_no_overpacked_hfid_fails_on_empty_hfid():
    tree = ast.parse(SRC_EMPTY_HFID)
    ok, msg = _mod.CHECKS["no-overpacked-hfid-list"](tree)
    assert not ok
    assert "device_type" in msg


SRC_THREE_FORMS = """
async def generate(self):
    site = await self.client.get(kind="LocationSite", name__value="PAR-1")
    device_type_uuid = "11111111-1111-1111-1111-111111111111"
    await self.client.create(
        kind="DcimDevice",
        data={
            "name": "cEdge-1",
            "manufacturer": {"hfid": ["Cisco"]},
            "device_type": {"id": device_type_uuid},
            "site": site,
        },
    )
"""


def test_hfid_form_for_name_lookup_passes_on_three_forms():
    tree = ast.parse(SRC_THREE_FORMS)
    ok, msg = _mod.CHECKS["hfid-form-for-name-lookup"](tree)
    assert ok, msg


def test_id_form_for_uuid_passes_on_three_forms():
    tree = ast.parse(SRC_THREE_FORMS)
    ok, msg = _mod.CHECKS["id-form-for-uuid"](tree)
    assert ok, msg


def test_sdk_object_reference_used_passes_on_three_forms():
    tree = ast.parse(SRC_THREE_FORMS)
    ok, msg = _mod.CHECKS["sdk-object-reference-used"](tree)
    assert ok, msg


def test_three_forms_fail_when_all_hfid():
    src = """
async def generate(self):
    await self.client.create(
        kind="DcimDevice",
        data={
            "name": "x",
            "manufacturer": {"hfid": ["Cisco"]},
            "device_type": {"hfid": ["cEdge-1000"]},
            "site": {"hfid": ["PAR-1"]},
        },
    )
"""
    tree = ast.parse(src)
    ok, _ = _mod.CHECKS["id-form-for-uuid"](tree)
    assert not ok
    ok, _ = _mod.CHECKS["sdk-object-reference-used"](tree)
    assert not ok


# Task 4 follow-up: missing negative coverage for hfid-form-for-name-lookup
def test_hfid_form_for_name_lookup_fails_when_none_use_hfid():
    src = """
async def generate(self):
    site = await self.client.get(kind="LocationSite", name__value="PAR-1")
    await self.client.create(
        kind="DcimDevice",
        data={
            "name": "x",
            "device_type": {"id": "abc-uuid"},
            "site": site,
        },
    )
"""
    tree = ast.parse(src)
    ok, _ = _mod.CHECKS["hfid-form-for-name-lookup"](tree)
    assert not ok


# Task 5 — Multi-peer add tests

SRC_GOOD_ADD_LOOP = """
async def generate(self):
    group = await self.client.get(kind="CoreStandardGroup", name__value="g")
    devices = [d1, d2, d3]
    for peer in devices:
        group.members.add(peer)
    await group.save()
"""

SRC_BAD_ADD_LIST = """
async def generate(self):
    group = await self.client.get(kind="CoreStandardGroup", name__value="g")
    devices = [d1, d2, d3]
    group.members.add(devices)
    await group.save()
"""

SRC_BAD_ADD_LIST_LITERAL = """
async def generate(self):
    group = await self.client.get(kind="CoreStandardGroup", name__value="g")
    group.members.add([d1, d2, d3])
    await group.save()
"""


def test_no_list_passed_to_add_passes_on_iteration():
    tree = ast.parse(SRC_GOOD_ADD_LOOP)
    ok, msg = _mod.CHECKS["no-list-passed-to-add"](tree)
    assert ok, msg


def test_no_list_passed_to_add_fails_on_list_literal():
    tree = ast.parse(SRC_BAD_ADD_LIST_LITERAL)
    ok, msg = _mod.CHECKS["no-list-passed-to-add"](tree)
    assert not ok


def test_no_list_passed_to_add_fails_on_list_named_variable():
    tree = ast.parse(SRC_BAD_ADD_LIST)
    ok, msg = _mod.CHECKS["no-list-passed-to-add"](tree)
    assert not ok


def test_members_add_iterates_passes_on_loop():
    tree = ast.parse(SRC_GOOD_ADD_LOOP)
    ok, msg = _mod.CHECKS["members-add-iterates"](tree)
    assert ok, msg


def test_members_add_iterates_fails_on_no_loop():
    tree = ast.parse(SRC_BAD_ADD_LIST_LITERAL)
    ok, msg = _mod.CHECKS["members-add-iterates"](tree)
    assert not ok


def test_members_add_iterates_fails_on_different_paths():
    """Two .add() calls on different attribute paths shouldn't be treated as iteration."""
    src = """
async def generate(self):
    group.members.add(d1)
    other.peers.add(d2)
"""
    tree = ast.parse(src)
    ok, msg = _mod.CHECKS["members-add-iterates"](tree)
    assert not ok, f"Should not pass — different paths, no loop. Got: {msg}"


# Task 6 — Natural-key preflight tests

SRC_PREFLIGHT = """
from infrahub_sdk.exceptions import NodeNotFound

async def create_prefix(client, user_prefix):
    try:
        existing = await client.get(kind="IpamPrefix", prefix__value=user_prefix)
        return existing
    except NodeNotFound:
        pass
    prefix = await client.create(kind="IpamPrefix", data={"prefix": user_prefix})
    await prefix.save()
"""

SRC_UPSERT = """
async def create_prefix(client, user_prefix):
    prefix = await client.create(kind="IpamPrefix", data={"prefix": user_prefix})
    await prefix.save(allow_upsert=True)
"""

SRC_UNSAFE = """
async def create_prefix(client, user_prefix):
    prefix = await client.create(kind="IpamPrefix", data={"prefix": user_prefix})
    await prefix.save()
"""


def test_preflight_or_upsert_passes_on_preflight():
    tree = ast.parse(SRC_PREFLIGHT)
    ok, _ = _mod.CHECKS["preflight-or-upsert"](tree)
    assert ok


def test_preflight_or_upsert_passes_on_upsert():
    tree = ast.parse(SRC_UPSERT)
    ok, _ = _mod.CHECKS["preflight-or-upsert"](tree)
    assert ok


def test_preflight_or_upsert_fails_on_unsafe():
    tree = ast.parse(SRC_UNSAFE)
    ok, _ = _mod.CHECKS["preflight-or-upsert"](tree)
    assert not ok
