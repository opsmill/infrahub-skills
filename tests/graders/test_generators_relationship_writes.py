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

# "concurrent-writes-use-add-relationships" only cares whether a
# RelationshipManager .add()/.extend() call on a shared (fetched, not
# run-private) node remains -- it is indifferent to how related_nodes is
# built. This phrasing exercises both narrowing exemptions at once: a
# local `set()` dedup (`seen.add(...)`, single-level, not a
# RelationshipManager at all) and a run-private node's own relationship
# (`device.tags.add(...)`, two-level, but `device` was created by this
# run and nobody else can be racing it). Both are correct and must not be
# reported alongside the real, shared-node add_relationships() call.
COMPLIANT_DIFFERENT = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    seen = set()
    peer_ids = []
    for spec in data["devices"]:
        if spec["id"] in seen:
            continue
        seen.add(spec["id"])
        peer_ids.append(spec["id"])
        device = await self.client.create(kind="DcimDevice", data=spec)
        await device.save(allow_upsert=True)
        device.tags.add("provisioned")
        await device.save(allow_upsert=True)
    await group.add_relationships(relation_to_update="members", related_nodes=peer_ids)
"""

VIOLATING = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    for device in data["devices"]:
        group.members.add(device["id"])
    await group.save(allow_upsert=True)
"""

# Near-miss for "concurrent-writes-use-add-relationships": add_relationships()
# is called (satisfies the check's keyword / a naive grep for it), but for a
# *different* relationship than the one being raced. The shared group is
# still mutated with extend()+save(), the same read-modify-write .add()
# is, just spelled differently -- and via a different node than whichever
# one add_relationships() happened to target, so a check that narrows by
# "same receiver as some add_relationships call" would wrongly pass this.
EXTEND_NEAR_MISS = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    other = await self.client.get(kind="CoreStandardGroup", name__value="other-edges")
    peer_ids = [d["id"] for d in data["devices"]]
    await other.add_relationships(relation_to_update="members", related_nodes=peer_ids)
    group.members.extend(peer_ids)
    await group.save(allow_upsert=True)
"""

# Near-miss for "concurrent-writes-use-add-relationships": a bare-name
# alias for a relationship access (`members = group.members`) is the same
# RelationshipManager as `group.members` written through a rename. Without
# resolving the alias, `members.add(...)` hits the single-level "not a
# RelationshipManager access" branch and is silently exempted, laundered by
# the unrelated `other.add_relationships(...)` call elsewhere in the file.
ALIAS_NEAR_MISS = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    other = await self.client.get(kind="CoreStandardGroup", name__value="other-edges")
    peer_ids = [d["id"] for d in data["devices"]]
    await other.add_relationships(relation_to_update="members", related_nodes=peer_ids)
    members = group.members
    for device in data["devices"]:
        members.add(device["id"])
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

# Compliant, phrased differently for "add-relationships-passes-ids": the
# rule's own Correct pattern writes `related_nodes=[p.id for p in peers]`,
# an inline list comprehension whose element is `p.id` (an ast.Attribute).
# COMPLIANT above never reaches that branch -- related_nodes there is a
# bare ast.Name -- so this fixture is what actually exercises it.
COMPLIANT_INLINE_LISTCOMP = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    peers = []
    for spec in data["devices"]:
        device = await self.client.create(kind="DcimDevice", data=spec)
        await device.save(allow_upsert=True)
        peers.append(device)
    await group.add_relationships(
        relation_to_update="members", related_nodes=[p.id for p in peers]
    )
"""

# Obviously violating for "add-relationships-passes-ids": a plain list
# literal holding a node object directly (the ast.List branch), distinct
# from NEAR_MISS's ast.Name-bound-to-a-list-built-by-append shape.
VIOLATING_NODE_LIST = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    device = await self.client.create(kind="DcimDevice", data=data["devices"][0])
    await device.save(allow_upsert=True)
    await group.add_relationships(relation_to_update="members", related_nodes=[device])
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


def test_near_miss_extend_on_different_shared_node_fails():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](
        tree=_tree(EXTEND_NEAR_MISS)
    )
    assert not ok
    assert ".extend()" in msg


def test_near_miss_alias_bypasses_narrowing_fails():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](
        tree=_tree(ALIAS_NEAR_MISS)
    )
    assert not ok
    assert ".add()" in msg
    assert "members.add" in msg


def test_ids_check_accepts_name_bound_to_comprehension():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(COMPLIANT))
    assert ok, msg


def test_ids_check_accepts_inline_comprehension():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(COMPLIANT_INLINE_LISTCOMP))
    assert ok, msg


def test_violating_node_list_fails():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(VIOLATING_NODE_LIST))
    assert not ok
    assert "node object" in msg.lower()


def test_near_miss_passing_node_objects_fails():
    ok, msg = CHECKS["add-relationships-passes-ids"](tree=_tree(NEAR_MISS))
    assert not ok
    assert "id" in msg.lower()
