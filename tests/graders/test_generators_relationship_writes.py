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


# `.extend()` is only a RelationshipManager write when it is reached
# through an attribute chain. A bare `names.extend([...])` on a local list
# shares the method name and nothing else -- without receiver narrowing it
# is the smallest edit that launders a non-answer into a pass on both
# `.add()` assertions, which is exactly the laundering graders.md forbids.
PLAIN_LIST_EXTEND_NO_PEER_WRITES = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    names = []
    names.extend([d["name"] for d in data["devices"]])
    await group.save()
"""

PLAIN_LIST_EXTEND_WITH_SINGLE_ADD = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    names = []
    names.extend([d["name"] for d in data["devices"]])
    group.members.add(data["devices"][0]["id"])
    await group.save()
"""

RELATIONSHIP_EXTEND_VIA_ALIAS = """
async def generate(self, data):
    group = await self.client.get(kind="CoreStandardGroup", name__value="sdwan-edges")
    members = group.members
    members.extend([d["id"] for d in data["devices"]])
    await group.save()
"""


def test_plain_list_extend_does_not_satisfy_members_add_iterates():
    ok, msg = CHECKS["members-add-iterates"](
        tree=_tree(PLAIN_LIST_EXTEND_NO_PEER_WRITES)
    )
    assert not ok, (
        "an answer that adds no group member at all must not pass just "
        f"because an unrelated local list was extended: {msg}"
    )


def test_plain_list_extend_does_not_satisfy_no_list_passed_to_add():
    ok, msg = CHECKS["no-list-passed-to-add"](
        tree=_tree(PLAIN_LIST_EXTEND_NO_PEER_WRITES)
    )
    assert not ok, (
        "with no RelationshipManager call in the answer there is nothing "
        f"to grade, so the 'nothing to grade' branch must fire: {msg}"
    )


def test_plain_list_extend_does_not_excuse_a_single_non_iterating_add():
    ok, msg = CHECKS["members-add-iterates"](
        tree=_tree(PLAIN_LIST_EXTEND_WITH_SINGLE_ADD)
    )
    assert not ok, (
        "one .add() outside a loop is still not per-peer iteration; an "
        f"unrelated list .extend() must not flip it to a pass: {msg}"
    )


def test_relationship_extend_through_an_alias_still_passes():
    ok, msg = CHECKS["members-add-iterates"](
        tree=_tree(RELATIONSHIP_EXTEND_VIA_ALIAS)
    )
    assert ok, (
        "`members = group.members` then `members.extend(...)` is a real "
        f"RelationshipManager write and must keep passing: {msg}"
    )


# `ast.walk` is breadth-first by depth, so an assignment nested in a loop is
# visited after every assignment at the outer level. A name rebound *after*
# the loop therefore resolved to the loop's value, and `_is_run_private_receiver`
# reported a shared fetched node as run-private -- exempting a real race from
# the concurrency check. Binding resolution is ordered by source position now.
REBIND_AFTER_LOOP_IS_NOT_RUN_PRIVATE = """
async def generate(self, data):
    for spec in data["items"]:
        device = await self.client.create(kind="DcimDevice", data=spec)
        await device.save(allow_upsert=True)
    device = await self.client.get(kind="DcimDevice", hfid="shared-tracker")
    device.tags.add("x")
    await device.save(allow_upsert=True)
    other = await self.client.get(kind="CoreStandardGroup", name__value="g")
    await other.add_relationships(
        relation_to_update="members", related_nodes=[d["id"] for d in data["x"]]
    )
"""

CREATED_IN_LOOP_STAYS_RUN_PRIVATE = """
async def generate(self, data):
    for spec in data["items"]:
        device = await self.client.create(kind="DcimDevice", data=spec)
        device.tags.add("x")
        await device.save(allow_upsert=True)
    group = await self.client.get(kind="CoreStandardGroup", name__value="g")
    await group.add_relationships(
        relation_to_update="members", related_nodes=[d["id"] for d in data["items"]]
    )
"""


def test_rebind_after_loop_is_not_treated_as_run_private():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](
        tree=ast.parse(REBIND_AFTER_LOOP_IS_NOT_RUN_PRIVATE)
    )
    assert not ok, (
        "device's live binding at the .tags.add() is a client.get() on a "
        f"fixed hfid, which is shared and races: {msg}"
    )
    assert "device.tags.add" in msg, msg


def test_node_created_in_a_loop_is_still_exempt():
    ok, msg = CHECKS["concurrent-writes-use-add-relationships"](
        tree=ast.parse(CREATED_IN_LOOP_STAYS_RUN_PRIVATE)
    )
    assert ok, f"a node this run created is run-private, even inside a loop: {msg}"


# `_is_node_object_expr` used to answer "was this name *ever* bound to a
# create/get call", not "what is it bound to here". Reassign-then-reuse is an
# ordinary way to write this and scored a false positive on compliant code.
REASSIGNED_TO_ID_BEFORE_USE = """
async def generate(self, data):
    device = await self.client.create(kind="DcimDevice", data=data["device"])
    await device.save(allow_upsert=True)
    device = device.id
    await group.add_relationships(relation_to_update="members", related_nodes=[device])
"""

STILL_A_NODE_OBJECT_AT_USE = """
async def generate(self, data):
    device = await self.client.create(kind="DcimDevice", data=data["device"])
    await device.save(allow_upsert=True)
    await group.add_relationships(relation_to_update="members", related_nodes=[device])
"""


def test_name_reassigned_to_id_before_use_passes():
    ok, msg = CHECKS["add-relationships-passes-ids"](
        tree=ast.parse(REASSIGNED_TO_ID_BEFORE_USE)
    )
    assert ok, f"device holds an id string by the time related_nodes reads it: {msg}"


def test_name_still_bound_to_node_object_at_use_fails():
    ok, msg = CHECKS["add-relationships-passes-ids"](
        tree=ast.parse(STILL_A_NODE_OBJECT_AT_USE)
    )
    assert not ok, f"device is still a node object at the call site: {msg}"


# --- delete ordering: detach peers before deleting them ---
#
# No eval task consumes these checks. That is deliberate and measured, not the
# oversight #147 was opened about; the PR for #147 carries the trial data and
# the reasoning, and `rules/python-delete-ordering.md` is the rule they encode.
#
# Be clear about what these fixtures do and do not guard. They pin the check
# functions' contract: that the ordering the rule prescribes passes, that the
# rule's own anti-pattern fails, and that vocabulary alone cannot launder a
# violation. They do NOT guard the rule's prose, because nothing grades an
# answer against it. If the prose is refactored away, these still pass.
#
# They are kept so the graded contract already exists, and is already proven to
# discriminate at fixture level, if a future model regresses far enough to make
# a task viable. DELETE_ANTIPATTERN is the sharpest of them: it is the shape
# `rules/python-delete-ordering.md` shows under "Anti-pattern", and the check
# removed in 814ffb7 passed it.

DELETE_COMPLIANT = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    stale_ids = [p.id for p in site.management_addresses.peers if p.id not in data["keep"]]
    for peer_id in stale_ids:
        site.management_addresses.remove(peer_id)
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
    for peer_id in stale_ids:
        address = await self.client.get(kind="IpamIPAddress", id=peer_id)
        await address.delete()
"""

DELETE_COMPLIANT_VARIANT = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    doomed = self._stale(site, data)
    await site.remove_relationships(
        relation_to_update="management_addresses", related_nodes=doomed
    )
    for identifier in doomed:
        site.management_addresses.remove(identifier)
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
    for identifier in doomed:
        await self.client.delete(kind="IpamIPAddress", id=identifier)
"""

DELETE_VIOLATING = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    for peer in site.management_addresses.peers:
        if peer.id not in data["keep"]:
            address = await self.client.get(kind="IpamIPAddress", id=peer.id)
            await address.delete()
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
"""

DELETE_NEAR_MISS_ITERATES_PEERS = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    doomed = []
    for peer in site.management_addresses.peers:
        if peer.id not in data["keep"]:
            doomed.append(peer.id)
            site.management_addresses.remove(peer.id)
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
    for peer_id in doomed:
        address = await self.client.get(kind="IpamIPAddress", id=peer_id)
        await address.delete()
"""

DELETE_ANTIPATTERN = """
async def generate(self, data):
    rack = await self.client.get(kind="DcimRack", id=data["rack"]["id"])
    for iface in data["stale"]:
        node = await self.client.get(kind="DcimInterface", id=iface["id"])
        await node.delete()
    await rack.save(allow_upsert=True)
"""

DELETE_LAUNDERED = '''
async def generate(self, data):
    """site.management_addresses.remove(peer_id) detaches before deleting."""
    # Detach first: site.management_addresses.remove(peer_id)
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    detach = "site.management_addresses.remove"
    for peer in site.management_addresses.peers:
        address = await self.client.get(kind="IpamIPAddress", id=peer.id)
        await address.delete()
    await site.save(allow_upsert=True)
'''

DELETE_ONLY_UNLINKS = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    stale_ids = [p.id for p in site.management_addresses.peers if p.id not in data["keep"]]
    for peer_id in stale_ids:
        site.management_addresses.remove(peer_id)
    await site.save(allow_upsert=True)
"""

DELETE_SERVER_SIDE_ONLY = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    doomed = [p.id for p in site.management_addresses.peers if p.id not in data["keep"]]
    await site.remove_relationships(
        relation_to_update="management_addresses", related_nodes=doomed
    )
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
    for identifier in doomed:
        await self.client.delete(kind="IpamIPAddress", id=identifier)
"""

DELETE_UNRELATED_CONTAINER_REMOVE = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    seen = [1, 2]
    seen.remove(1)
    self.cache.remove("x")
    for peer in site.management_addresses.peers:
        address = await self.client.get(kind="IpamIPAddress", id=peer.id)
        await address.delete()
    await site.save(allow_upsert=True)
"""


def test_delete_compliant_passes():
    for name in ("peer-delete-present", "detach-precedes-peer-delete", "detach-iterates-id-list"):
        ok, msg = CHECKS[name](tree=_tree(DELETE_COMPLIANT))
        assert ok, f"{name} failed the rule's own correct pattern: {msg}"


def test_delete_compliant_variant_passes():
    for name in ("peer-delete-present", "detach-precedes-peer-delete", "detach-iterates-id-list"):
        ok, msg = CHECKS[name](tree=_tree(DELETE_COMPLIANT_VARIANT))
        assert ok, f"{name} failed a helper/server-side phrasing of the same order: {msg}"


def test_delete_violating_fails_on_ordering():
    ok, msg = CHECKS["detach-precedes-peer-delete"](tree=_tree(DELETE_VIOLATING))
    assert not ok, "peers deleted while the site still holds them should fail"
    assert "remove" in msg


def test_delete_near_miss_iterating_peers_fails():
    ordering_ok, _ = CHECKS["detach-precedes-peer-delete"](
        tree=_tree(DELETE_NEAR_MISS_ITERATES_PEERS)
    )
    assert ordering_ok, "the near miss orders detach/save/delete correctly on purpose"
    ok, msg = CHECKS["detach-iterates-id-list"](
        tree=_tree(DELETE_NEAR_MISS_ITERATES_PEERS)
    )
    assert not ok, "iterating .peers while removing from it should fail"
    assert "skipped" in msg


def test_rule_antipattern_is_caught():
    """The shape the replaced check passed. This is why #147 existed."""
    ok, msg = CHECKS["detach-precedes-peer-delete"](tree=_tree(DELETE_ANTIPATTERN))
    assert not ok, f"the rule's own anti-pattern must fail: {msg}"


def test_delete_vocabulary_does_not_launder():
    ok, _ = CHECKS["detach-precedes-peer-delete"](tree=_tree(DELETE_LAUNDERED))
    assert not ok, "a docstring, a comment and a bare string must not satisfy the check"


def test_delete_unlink_without_delete_is_not_a_peer_delete():
    ok, msg = CHECKS["peer-delete-present"](tree=_tree(DELETE_ONLY_UNLINKS))
    assert not ok, f"unlinking without deleting leaves the peers in Infrahub: {msg}"


def test_server_side_detach_alone_fails_when_the_node_is_saved():
    """remove_relationships() never touches the in-memory manager."""
    ok, msg = CHECKS["detach-precedes-peer-delete"](tree=_tree(DELETE_SERVER_SIDE_ONLY))
    assert not ok, f"the save re-sends the ids remove_relationships() dropped: {msg}"


def test_unrelated_container_remove_is_not_a_detach():
    ok, _ = CHECKS["detach-precedes-peer-delete"](
        tree=_tree(DELETE_UNRELATED_CONTAINER_REMOVE)
    )
    assert not ok, "list.remove() and self.cache.remove() are not relationship detaches"


# Hydrated peers: the skill's own hydration rule (and check_no_client_get_in_loop)
# push generators to build peers with from_graphql off the query payload rather
# than re-fetching each one. A red run produced exactly this shape and an earlier
# draft of _peer_delete_calls reported it as "never deleted".

DELETE_COMPLIANT_HYDRATED = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    stale_ids = [e["node"]["id"] for e in data["stale"]["edges"]]
    for peer_id in stale_ids:
        site.management_addresses.remove(peer_id)
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
    for edge in data["stale"]["edges"]:
        node = InfrahubNode.from_graphql(self.client, self.branch, edge["node"])
        await node.delete()
"""

DELETE_VIOLATING_HYDRATED = """
async def generate(self, data):
    site = await self.client.get(kind="LocationSite", id=data["site"]["id"])
    for edge in data["stale"]["edges"]:
        node = InfrahubNode.from_graphql(self.client, self.branch, edge["node"])
        await node.delete()
    site.description.value = data["description"]
    await site.save(allow_upsert=True)
"""


def test_hydrated_peer_delete_is_recognised():
    ok, msg = CHECKS["peer-delete-present"](tree=_tree(DELETE_COMPLIANT_HYDRATED))
    assert ok, f"a from_graphql-hydrated node's .delete() is still a delete: {msg}"


def test_hydrated_compliant_passes_ordering():
    ok, msg = CHECKS["detach-precedes-peer-delete"](
        tree=_tree(DELETE_COMPLIANT_HYDRATED)
    )
    assert ok, f"detach, save, then delete is correct however the peer was built: {msg}"


def test_hydrated_violating_fails_ordering():
    ok, msg = CHECKS["detach-precedes-peer-delete"](
        tree=_tree(DELETE_VIOLATING_HYDRATED)
    )
    assert not ok, f"deleting before the save is wrong however the peer was built: {msg}"
