"""Fixture tests for the concurrent relationship write checks."""

import ast
import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "managing-generators" / "lib.py"
_spec = importlib.util.spec_from_file_location(
    "managing_generators_graders_lib", _LIB_PATH
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

CHECKS = _mod.CHECKS


def _tree(src: str) -> ast.Module:
    return ast.parse(src)


COMPLIANT = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    peer_ids = [d["id"] for d in data["devices"]]
    await group.add_relationships(
        relation_to_update="members", related_nodes=peer_ids
    )
"""

COMPLIANT_DIFFERENT = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    ids = []
    for device in data["devices"]:
        ids.append(device["id"])
    await group.add_relationships(relation_to_update="members", related_nodes=ids)
"""

VIOLATING = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    for device in data["devices"]:
        group.members.add(device["id"])
    await group.save(allow_upsert=True)
"""

NEAR_MISS = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    nodes = []
    for spec in data["devices"]:
        node = await self.client.create(kind="DcimDevice", data=spec)
        await node.save(allow_upsert=True)
        nodes.append(node)
    await group.add_relationships(
        relation_to_update="members", related_nodes=nodes
    )
"""


def test_compliant_passes():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](tree=_tree(COMPLIANT))
    assert ok, msg


def test_compliant_phrased_differently_passes():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](
        tree=_tree(COMPLIANT_DIFFERENT)
    )
    assert ok, msg


def test_violating_fails():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](tree=_tree(VIOLATING))
    assert not ok
    assert ".add()" in msg


def test_near_miss_passing_node_objects_fails():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(NEAR_MISS))
    assert not ok
    assert "id" in msg.lower()


def test_ids_check_accepts_comprehension():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(COMPLIANT))
    assert ok, msg
