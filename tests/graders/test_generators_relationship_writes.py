"""Fixture tests for the concurrent relationship write checks."""

import ast
import importlib.util
import json
import subprocess
import sys
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


EXTEND_COMPLIANT = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    group.members.extend([d["id"] for d in data["devices"]])
    await group.save(allow_upsert=True)
"""


def test_extend_counts_as_per_peer_iteration():
    ok, msg = CHECKS["members-add-iterates"](tree=_tree(EXTEND_COMPLIANT))
    assert ok, msg


def test_extend_only_passes_no_list_passed_to_add():
    """Fix round 1, finding 1: an .extend()-only answer has no .add() call
    for "no list passed to .add()" to fail against, so it must pass.
    """
    ok, msg = CHECKS["no-list-passed-to-add"](tree=_tree(EXTEND_COMPLIANT))
    assert ok, msg


# Fix round 1, finding 2: a nested list inside .extend()'s argument
# reproduces the exact composite-HFID bug the rule exists to prevent, one
# level deeper. `[[d["id"]] for d in data["devices"]]` builds a list of
# one-element lists, so each peer .extend() would hand to .add() is
# itself a list, not a scalar id.
EXTEND_NESTED_LIST_LITERAL = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    group.members.extend([["peer-a"], ["peer-b"]])
    await group.save(allow_upsert=True)
"""

EXTEND_NESTED_LIST_VIA_NAME = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    grouped_ids = [["peer-a"], ["peer-b"]]
    group.members.extend(grouped_ids)
    await group.save(allow_upsert=True)
"""


def test_extend_nested_list_literal_fails():
    ok, msg = CHECKS["no-list-passed-to-add"](tree=_tree(EXTEND_NESTED_LIST_LITERAL))
    assert not ok
    assert "nested list" in msg.lower()


def test_extend_nested_list_via_name_fails():
    ok, msg = CHECKS["no-list-passed-to-add"](tree=_tree(EXTEND_NESTED_LIST_VIA_NAME))
    assert not ok
    assert "nested list" in msg.lower()


# Indeterminate arguments to .extend() (a ListComp, not a resolvable list
# literal) pass, per the house indeterminate-passes convention -- this
# check cannot tell whether `[d["id"] for d in data["devices"]]` produces
# scalars or nested lists without running it.
def test_extend_listcomp_argument_is_indeterminate_and_passes():
    ok, msg = CHECKS["no-list-passed-to-add"](tree=_tree(EXTEND_COMPLIANT))
    assert ok, msg


# Fix round 1, finding 3: a valid generator can call both .extend() (for
# the bulk of the peers) and a standalone .add() (for one more, added
# outside the loop). Presence of .extend() must satisfy per-peer
# iteration regardless of what else is in the file.
EXTEND_PLUS_STANDALONE_ADD = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    group.members.extend([d["id"] for d in data["devices"]])
    group.members.add("extra-peer-id")
    await group.save(allow_upsert=True)
"""


def test_extend_plus_standalone_add_still_iterates():
    ok, msg = CHECKS["members-add-iterates"](tree=_tree(EXTEND_PLUS_STANDALONE_ADD))
    assert ok, msg


# ---------------------------------------------------------------------------
# End-to-end: drive the actual grader script, not CHECKS[...] in isolation.
#
# Fix round 1 was found by running check_multi_peer_iteration.py end to
# end against a compliant .extend()-only answer and seeing it score 0.5,
# not by calling CHECKS["no-list-passed-to-add"] directly -- that call in
# isolation never exercises how the eval bundles two checks together at
# weight 1.0. This test drives the script the same way skillgrade does,
# so a regression in that bundling fails here again.
# ---------------------------------------------------------------------------

_GRADER_SCRIPT = _REPO_ROOT / "graders" / "managing-generators" / "check_multi_peer_iteration.py"


def _run_multi_peer_iteration_grader(source: str, tmp_path: Path) -> dict:
    (tmp_path / "output.py").write_text(source)
    result = subprocess.run(
        [sys.executable, str(_GRADER_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, (
        f"check_multi_peer_iteration.py exited with code {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return json.loads(result.stdout)


def test_grader_script_scores_extend_only_answer_full_marks(tmp_path):
    data = _run_multi_peer_iteration_grader(EXTEND_COMPLIANT, tmp_path)
    assert data["score"] == 1.0, data["details"]
    for check in data["checks"]:
        assert check["passed"], check


def test_grader_script_still_scores_for_loop_answer_full_marks(tmp_path):
    data = _run_multi_peer_iteration_grader(VIOLATING, tmp_path)
    # VIOLATING is named for the concurrent-writes check (a for-loop of
    # .add() on a shared node is unsafe there); for this grader script it
    # is the textbook correct for-loop-of-.add() answer and must still
    # score full marks after the fix.
    assert data["score"] == 1.0, data["details"]


DELETE_COMPLIANT = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    for iface in rack.interfaces.peers:
        rack.interfaces.remove(iface.id)
    await rack.save(allow_upsert=True)
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
"""

DELETE_COMPLIANT_DIFFERENT = """
async def _detach(rack, ids):
    for peer_id in ids:
        rack.interfaces.remove(peer_id)
    await rack.save(allow_upsert=True)


async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    await _detach(rack, [i["id"] for i in data["stale"]])
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
"""

DELETE_VIOLATING = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

DELETE_NEAR_MISS = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    for iface in data["stale"]:
        rack.interfaces.remove(iface["id"])
    await rack.save(allow_upsert=True)
"""

DELETE_COMMENT_ONLY = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    # Detach the interfaces before deleting the peers.
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""


def test_delete_compliant_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_COMPLIANT))
    assert ok, msg


def test_delete_compliant_via_helper_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_COMPLIANT_DIFFERENT)
    )
    assert ok, msg


def test_delete_violating_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_VIOLATING))
    assert not ok


def test_delete_near_miss_remove_after_delete_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_NEAR_MISS))
    assert not ok, "a .remove() placed after .delete() must not satisfy the check"
    assert "after" in msg


def test_delete_comment_only_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_COMMENT_ONLY))
    assert not ok, "a comment saying 'detach' must not satisfy the check"


DELETE_NO_SAVE_NO_RISK = """
async def generate(self, data):
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
"""

DELETE_SINGLE_NODE_NO_RISK = """
async def generate(self, data):
    node = await self.client.get(kind="DcimInterface", id=data["id"])
    await node.delete()
"""

DELETE_LAUNDERED_WITH_UNRELATED_REMOVE = """
async def generate(self, data):
    seen = []
    seen.remove(1)
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""


def test_delete_with_no_save_call_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_NO_SAVE_NO_RISK))
    assert ok, (
        "no save() call exists anywhere, so no RelationshipManager could "
        f"re-send a deleted peer: {msg}"
    )


def test_delete_single_unrelated_node_with_no_save_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_SINGLE_NODE_NO_RISK)
    )
    assert ok, (
        "a lone node deleted with nothing saved afterwards has nothing at "
        f"risk: {msg}"
    )


def test_delete_laundered_with_unrelated_remove_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_LAUNDERED_WITH_UNRELATED_REMOVE)
    )
    assert not ok, (
        "a .remove() on a bare local (seen.remove(1)) must not satisfy the "
        "check just because a .remove() token appears before the .delete()"
    )
