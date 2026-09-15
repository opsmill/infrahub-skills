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


# --- detach-before-peer-delete: the exact four-condition matrix ---
#
# Flag only when all four hold: (1) a .delete() on a node this module
# itself obtained; (2) some node variable N has a relationship attribute
# accessed as N.<rel> somewhere (an .add()/.extend()/.remove() call on it,
# a .peers read, or direct iteration -- never a bare attribute read); (3)
# N.save(...) runs after that .delete() in source order; (4) no
# N.<rel>.remove(...) runs before that .delete(). Any shape that cannot be
# resolved this way is left alone -- a missed violation is the accepted
# trade for never failing ordinary code.

DELETE_COMPLIANT = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = [iface["id"] for iface in data["stale"]]
    for peer_id in stale_ids:
        rack.interfaces.remove(peer_id)
    await rack.save(allow_upsert=True)
    for peer_id in stale_ids:
        node = await self.client.get(kind="DcimInterface", id=peer_id)
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

# Case 1: peers deleted, nothing holds them, an unrelated save() elsewhere.
# `other.name` is a plain attribute, never touched with .add/.extend/.remove
# or .peers, so it is never mistaken for a relationship manager.
DELETE_UNRELATED_SAVE_NO_RISK = """
async def generate(self, data):
    other = await self.client.get(kind="CoreStandardGroup", name__value="g")
    other.name.value = "renamed"
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await other.save(allow_upsert=True)
"""

# Case 2: the parent demonstrably holds the deleted peers (it reads
# rack.interfaces.peers) and is saved after the delete, with no detach.
# `kept` is load-bearing -- it drives the description set on rack -- so
# this is a generator that genuinely reads its peers before deleting some
# of them, not a line added only to satisfy the check.
DELETE_VIOLATING = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = {i["id"] for i in data["stale"]}
    kept = [p.id for p in rack.interfaces.peers if p.id not in stale_ids]
    rack.description.value = f"kept {len(kept)} interfaces"
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

# Case 3: a bare local's .remove() (seen.remove(1)) sits before the delete,
# but it is not rack.interfaces.remove(...), so it must not launder this.
DELETE_LAUNDERED_BARE_LOCAL = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = {i["id"] for i in data["stale"]}
    kept = [p.id for p in rack.interfaces.peers if p.id not in stale_ids]
    seen = []
    seen.remove(1)
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

# Case 4: an attribute-chain .remove() on an unrelated receiver
# (self.cache) sits before the delete; still not rack.interfaces.remove().
DELETE_LAUNDERED_UNRELATED_ATTR_CACHE = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = {i["id"] for i in data["stale"]}
    kept = [p.id for p in rack.interfaces.peers if p.id not in stale_ids]
    self.cache.remove(0)
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

# Case 5: same shape, the smallest-edit laundering the reviewer proposed --
# a plausible bookkeeping list (self.processed) instead of self.cache.
DELETE_LAUNDERED_UNRELATED_ATTR_PROCESSED = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = {i["id"] for i in data["stale"]}
    kept = [p.id for p in rack.interfaces.peers if p.id not in stale_ids]
    self.processed.remove(0)
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

# Case 7: .remove() on the real relationship, but placed after .delete().
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

# Case 8: a node with no relationships, deleted alone, no saves.
DELETE_SINGLE_NODE_NO_RISK = """
async def generate(self, data):
    node = await self.client.get(kind="DcimInterface", id=data["id"])
    await node.delete()
"""

# Extra no-risk case: same shape as case 8 but a loop, still no save.
DELETE_NO_SAVE_NO_RISK = """
async def generate(self, data):
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
"""

# Case 9: the same violation as case 2, but the delete is written as a
# direct self.client.delete(kind=..., id=...) call -- dropping the
# unnecessary fetch a model would naturally do -- rather than
# node = await self.client.get(...); await node.delete().
DELETE_CLIENT_DELETE_VIOLATING = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    stale_ids = {i["id"] for i in data["stale"]}
    kept = [p.id for p in rack.interfaces.peers if p.id not in stale_ids]
    rack.description.value = f"kept {len(kept)} interfaces"
    for iface in data["stale"]:
        await self.client.delete(kind="DcimInterface", id=iface["id"])
    await rack.save(allow_upsert=True)
"""

# Case 10: same self.client.delete(...) shape as case 9, but nothing holds
# the deleted peers -- the save is on an unrelated node.
DELETE_CLIENT_DELETE_NO_RISK = """
async def generate(self, data):
    other = await self.client.get(kind="CoreStandardGroup", name__value="g")
    other.name.value = "renamed"
    for iface in data["stale"]:
        await self.client.delete(kind="DcimInterface", id=iface["id"])
    await other.save(allow_upsert=True)
"""


def test_delete_compliant_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_COMPLIANT))
    assert ok, msg


def test_delete_compliant_via_helper_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_COMPLIANT_DIFFERENT)
    )
    assert ok, msg


def test_delete_unrelated_save_no_risk_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_UNRELATED_SAVE_NO_RISK)
    )
    assert ok, (
        "a save() on a node that never touches a relationship manager must "
        f"not be mistaken for the one holding the deleted peers: {msg}"
    )


def test_delete_violating_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_VIOLATING))
    assert not ok, msg


def test_delete_laundered_bare_local_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_LAUNDERED_BARE_LOCAL)
    )
    assert not ok, (
        "a .remove() on a bare local (seen.remove(1)) must not satisfy the "
        "check just because a .remove() token appears before the .delete()"
    )


def test_delete_laundered_unrelated_attr_cache_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_LAUNDERED_UNRELATED_ATTR_CACHE)
    )
    assert not ok, (
        "a .remove() on an unrelated attribute chain (self.cache) must not "
        "satisfy the check; only rack.interfaces.remove() detaches rack"
    )


def test_delete_laundered_unrelated_attr_processed_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_LAUNDERED_UNRELATED_ATTR_PROCESSED)
    )
    assert not ok, (
        "self.processed.remove(0) is bookkeeping, not a detach of "
        "rack.interfaces, and must not launder the check"
    )


def test_delete_near_miss_remove_after_delete_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_NEAR_MISS))
    assert not ok, "a .remove() placed after .delete() must not satisfy the check"
    assert "after" in msg or "rack.interfaces" in msg


def test_delete_single_unrelated_node_with_no_save_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_SINGLE_NODE_NO_RISK)
    )
    assert ok, (
        "a lone node deleted with nothing saved afterwards has nothing at "
        f"risk: {msg}"
    )


def test_delete_with_no_save_call_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](tree=ast.parse(DELETE_NO_SAVE_NO_RISK))
    assert ok, (
        "no save() call exists anywhere, so no RelationshipManager could "
        f"re-send a deleted peer: {msg}"
    )


def test_delete_via_client_delete_call_fails():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_CLIENT_DELETE_VIOLATING)
    )
    assert not ok, (
        "self.client.delete(kind=..., id=...) is a real peer-delete site "
        f"and must not bypass the check just by skipping the fetch: {msg}"
    )


def test_delete_via_client_delete_call_with_no_risk_passes():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_CLIENT_DELETE_NO_RISK)
    )
    assert ok, (
        "self.client.delete(...) with nothing holding the deleted peers "
        f"must still pass, same as the node.delete() shape: {msg}"
    )


# KNOWN LIMITATION, not endorsed: the check cannot correlate which object
# a recognised delete actually removed with which relationship's peers.
# It only asks whether *some* recognised delete and *some* node with a
# demonstrated relationship co-occur with an unguarded save. Here the
# deleted CoreStandardGroup has nothing to do with rack.interfaces, and
# this is otherwise compliant code, but the check still flags it -- see
# the docstring of check_detach_before_peer_delete for why no static
# narrowing closes this gap without also losing the real violation case.
# If this test starts failing because someone closed the correlation gap,
# update it to assert `ok` instead of deleting it.
DELETE_KNOWN_FALSE_POSITIVE_UNRELATED_DELETE = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", name__value="rack-1")
    kept = [p.id for p in rack.interfaces.peers]
    rack.description.value = f"kept {len(kept)} interfaces"
    await self.client.delete(kind="CoreStandardGroup", id=data["unrelated_group_id"])
    await rack.save(allow_upsert=True)
"""


def test_known_false_positive_unrelated_delete_is_flagged():
    ok, msg = CHECKS["detach-before-peer-delete"](
        tree=ast.parse(DELETE_KNOWN_FALSE_POSITIVE_UNRELATED_DELETE)
    )
    assert not ok, (
        "documents a known limitation, not a goal: the check cannot tell "
        "that the deleted CoreStandardGroup has no relation to "
        f"rack.interfaces, so this ordinary code is (wrongly) flagged: {msg}"
    )
