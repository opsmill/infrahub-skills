"""Tests for the report checks in graders/harvesting-release-notes/lib.py.

The task grader runs against four report fixtures under
fixtures/harvesting-release-notes/deprecation_removal/: compliant, compliant
variant, violating, and violating near miss. Each case is assembled into a
workspace the way skillgrade builds the sandbox: the fixture skill files are
copied in under their `.md` names and the report is written to REPORT.md.

The variant moves what the checks read, not the cosmetics: the target finding
is second, after an UNVERIFIED finding with no gate; the evidence is a commit
SHA; the gate spans two lines with its clauses reversed; the location is a
line range in backticks; the severity carries a trailing reason.

The near miss carries every field, pinned evidence, and a two-sided gate that
keeps `name__like`, but names only 1.6. It must fail on gate-boundaries and
nothing else, so a check that only looks for a version and a "before" clause
cannot pass it.

Fixtures are `.txt` so rumdl does not reformat them and the CLI invocation
gate does not scan them; the eval.yaml workspace mapping renames them.
"""

import ast
import hashlib
import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GRADER_DIR = _REPO_ROOT / "graders" / "harvesting-release-notes"
_FIXTURES = (
    Path(__file__).resolve().parent / "fixtures" / "harvesting-release-notes" / "deprecation_removal"
)
# The sandbox files, flat and short-named so eval.yaml's workspace mapping
# stays under yamllint's line length; the mapping gives each its real path.
_WORKSPACE = _FIXTURES / "ws"
_SKILL_SRC = {
    "skills/acme-querying-inventory/SKILL.md": _WORKSPACE / "skill-SKILL.txt",
    "skills/acme-querying-inventory/rules/filters.md": _WORKSPACE / "skill-filters.txt",
}
_TASK = "harvest-release-notes-deprecation-removal"

_spec = importlib.util.spec_from_file_location(
    "harvesting_release_notes_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks
CHECKS = _mod.CHECKS


def _script_constant(name: str):
    tree = ast.parse((_GRADER_DIR / "check_deprecation_removal.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"check_deprecation_removal.py defines no {name}")


def _task_checks() -> list:
    """The CHECKS list with the AFFECTED and SKILL_FILES names resolved."""
    tree = ast.parse((_GRADER_DIR / "check_deprecation_removal.py").read_text())
    env = {"AFFECTED": _script_constant("AFFECTED"), "SKILL_FILES": _script_constant("SKILL_FILES")}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "CHECKS" for t in node.targets
        ):
            return eval(compile(ast.Expression(node.value), "<checks>", "eval"), {}, env)  # noqa: S307
    raise AssertionError("check_deprecation_removal.py defines no CHECKS")


def _workspace(tmp_path: Path, case: str) -> Path:
    for rel, src in _SKILL_SRC.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, tmp_path / rel)
    if case == "fail":
        shutil.copy(
            _FIXTURES / "fail-skill-filters.txt",
            tmp_path / "skills" / "acme-querying-inventory" / "rules" / "filters.md",
        )
    report = tmp_path / "REPORT.md"
    shutil.copy(_FIXTURES / f"{case}.txt", report)
    return report


def _failed(result: dict) -> list[str]:
    return [c["name"] for c in result["checks"] if not c["passed"]]


@pytest.mark.parametrize("case", ["pass", "pass-variant"])
def test_compliant_fixture_scores_full(tmp_path, case):
    result = run_checks(_task_checks(), _workspace(tmp_path, case))
    assert result["score"] == 1.0, result["checks"]


def _messages(result: dict) -> dict[str, str]:
    return {c["name"]: c["message"] for c in result["checks"] if not c["passed"]}


def test_violating_fixture_fails_on_the_gate_and_the_edit(tmp_path):
    """Each failure names the shape that broke, not only the check."""
    result = run_checks(_task_checks(), _workspace(tmp_path, "fail"))
    messages = _messages(result)
    assert result["score"] < 1.0
    assert "'Deprecated in' is 'none', expected 1.6" in messages["gate-boundaries"]
    assert "No Gate clause keeps 'name__like' up to 1.6" in messages["gate-keeps-old-guidance"]
    assert "names no source path" in messages["evidence-pinned"]
    assert "rules/filters.md was edited" in messages["skill-unchanged"]


def test_near_miss_fails_only_on_gate_boundaries(tmp_path):
    result = run_checks(_task_checks(), _workspace(tmp_path, "fail-nearmiss"))
    assert _messages(result) == {"gate-boundaries": "Gate names 1.6; expected exactly 1.6, 1.7"}


def _gate_report(gate: str) -> str:
    return (_FIXTURES / "pass.txt").read_text().replace(
        "- Gate: `name__contains` is available from Infrahub 1.6 and required from 1.7. "
        "Before 1.7: `name__like` still works.",
        f"- Gate: {gate}",
    )


_KEEPS_OLD = {
    "affected_path": "skills/acme-querying-inventory/rules/filters.md",
    "old_token": "name__like",
    "new_token": "name__contains",
    "removed": "1.7",
    "deprecated": "1.6",
}


@pytest.mark.parametrize(
    "gate",
    [
        "Before 1.7: `name__like`. From 1.6: `name__contains`, required from 1.7.",
        "Infrahub 1.6 and earlier: `name__like` still works; `name__contains` from 1.6, required from 1.7.",
        "Up to 1.6: `name__like`. Available from 1.6 and required from 1.7: `name__contains`.",
        # A live trial: the switch happens where the new filter became
        # available, so every release still has working guidance.
        "Infrahub 1.6 and later: use `name__contains`. It is required from 1.7, where `name__like` "
        "fails. Before 1.6: `name__like` is the only substring filter and still works.",
        # The clause that keeps the old filter also says when it stops working.
        "From 1.6: `name__contains`, required from 1.7. Before 1.6: `name__like` still works, "
        "but it fails from 1.7.",
        "Infrahub 1.6.0 and later: use `name__contains`. It is required from 1.7.0, which removed "
        "`name__like`. Before 1.6.0: `name__like`.",
    ],
)
def test_keeps_old_guidance_accepts_a_clause_reaching_the_removal(gate):
    ok, msg = _mod.check_gate_keeps_old_guidance(_gate_report(gate), root=Path("."), **_KEEPS_OLD)
    assert ok, msg


@pytest.mark.parametrize(
    "gate",
    [
        # Names 1.6 and 1.7, keeps the old filter, but leaves 1.6.x uncovered.
        "From 1.7: `name__contains`. Before 1.6: `name__like`.",
        # The old filter stops before the new one is available.
        "Before 1.5: `name__like`. From 1.6: `name__contains`, required from 1.7.",
        # Past the removal: 1.7 has no `name__like`, so neither clause is true.
        "Before 1.8: `name__like`. From 1.6: `name__contains`, required from 1.7.",
        "Infrahub 1.7 and earlier: `name__like`. From 1.6: `name__contains`, required from 1.7.",
        # The old filter appears only in the clause that removes it.
        "1.7 and later: `name__like` is removed, use `name__contains` (available from 1.6).",
        # The old guidance kept with no version at all.
        "From 1.6 use `name__contains`, required from 1.7. Earlier: `name__like`.",
    ],
)
def test_keeps_old_guidance_rejects_a_clause_that_stops_short(gate):
    ok, msg = _mod.check_gate_keeps_old_guidance(_gate_report(gate), root=Path("."), **_KEEPS_OLD)
    assert not ok, msg


def test_a_field_ends_at_the_first_blank_line(tmp_path):
    """Prose after the field list is not part of the last field. A paragraph
    naming another version after `Gate:` must not change what the gate names,
    and one after an UNVERIFIED finding's `Gate: none` must not turn it into a
    recommendation."""
    report = _workspace(tmp_path, "pass")
    report.write_text(
        report.read_text().replace(
            "## Not reported",
            "Why High: on 1.8 and 1.9 the query still fails the same way.\n\n## Not reported",
        )
    )
    result = run_checks(_task_checks(), report)
    assert result["score"] == 1.0, result["checks"]

    unverified = (
        "### Finding 2\n\n- Repository: opsmill/infrahub\n- Severity: Medium\n"
        "- Affected: skills/acme-querying-inventory/SKILL.md:15\n- Deprecated in: none\n"
        "- Removed in: none\n- Verified in: UNVERIFIED\n- Gate: none\n\n"
        "The notes mention this, but the source did not confirm it.\n"
    )
    report.write_text(report.read_text() + "\n" + unverified)
    ok, msg = _mod.check_evidence_pinned(report.read_text(), start="1.6.0", end="1.7.0")
    assert ok, msg


_VERIFIED = "- Verified in: infrahub-v1.7.0:backend/infrahub/graphql/filters.py"


@pytest.mark.parametrize(
    ("verified", "ok"),
    [
        # Both ends of the range are inside it; one release past either end is not.
        ("infrahub-v1.6.0:backend/infrahub/graphql/filters.py", True),
        ("infrahub-v1.7.0:backend/infrahub/graphql/filters.py", True),
        ("infrahub-v1.5.9:backend/infrahub/graphql/filters.py", False),
        ("infrahub-v1.8.0:backend/infrahub/graphql/filters.py", False),
        # Seven hex characters pin a commit; six do not.
        ("abcdef1:backend/infrahub/graphql/filters.py", True),
        ("abcdef:backend/infrahub/graphql/filters.py", False),
        # A path with nothing pinning it.
        ("backend/infrahub/graphql/filters.py", False),
    ],
)
def test_evidence_pinned_boundaries(verified, ok):
    report = (_FIXTURES / "pass.txt").read_text().replace(_VERIFIED, f"- Verified in: {verified}")
    passed, msg = _mod.check_evidence_pinned(report, start="1.6.0", end="1.7.0")
    assert passed is ok, msg


def test_a_prerelease_cited_in_any_field_fails():
    """Not only the three version fields: a beta named in the gate is cited too."""
    report = _gate_report(
        "From infrahub-v1.7.0b1 use `name__contains`; available from 1.6. Before 1.7: `name__like`."
    )
    passed, msg = _mod.check_evidence_pinned(report, start="1.6.0", end="1.7.0")
    assert not passed
    assert "'gate' cites a pre-release (1.7.0b1)" in msg


def test_affected_paths_must_exist(tmp_path):
    """A change that touches no passage is not a finding. A finding for one
    names a file that is not there, or a line past the end of the file."""
    report = _workspace(tmp_path, "pass")
    assert _mod.check_affected_paths_exist(report.read_text(), root=tmp_path)[0]

    lines = len((tmp_path / "skills/acme-querying-inventory/rules/filters.md").read_text().splitlines())
    last = report.read_text().replace("rules/filters.md:9", f"rules/filters.md:{lines}")
    assert _mod.check_affected_paths_exist(last, root=tmp_path)[0]

    past_end = report.read_text().replace("rules/filters.md:9", f"rules/filters.md:{lines + 1}")
    ok, msg = _mod.check_affected_paths_exist(past_end, root=tmp_path)
    assert not ok
    assert f"rules/filters.md:{lines + 1} is past the end" in msg

    invented = report.read_text().replace(
        "## Not reported",
        "### Finding 2\n\n- Repository: opsmill/infrahub\n- Severity: Medium\n"
        "- Affected: skills/acme-querying-inventory/rules/cache.md:3\n- Deprecated in: none\n"
        "- Removed in: infrahub-v1.7.0\n- Verified in: infrahub-v1.7.0:backend/infrahub/config.py\n"
        "- Gate: Before 1.7: set `INFRAHUB_LEGACY_CACHE`.\n\n## Not reported",
    )
    ok, msg = _mod.check_affected_paths_exist(invented, root=tmp_path)
    assert not ok
    assert "Finding 2 names skills/acme-querying-inventory/rules/cache.md, which does not exist" in msg


def test_missing_report_fails(tmp_path):
    result = run_checks(_task_checks(), tmp_path / "REPORT.md")
    assert result["score"] < 1.0
    assert "report-has-findings" in _failed(result)


def test_task_grader_names_only_registered_checks():
    for spec in _task_checks():
        name = spec[0] if isinstance(spec, tuple) else spec
        assert name in CHECKS, name


def test_skill_hashes_match_the_workspace_fixtures():
    pinned = _script_constant("SKILL_FILES")
    assert set(pinned) == set(_SKILL_SRC)
    for rel, path in _SKILL_SRC.items():
        assert pinned[rel] == hashlib.sha256(path.read_bytes()).hexdigest(), rel


def _eval_task() -> dict:
    data = yaml.safe_load((_REPO_ROOT / "eval.yaml").read_text())
    for task in data["tasks"]:
        if task["name"] == _TASK:
            return task
    raise AssertionError(f"eval.yaml has no task {_TASK}")


def test_eval_workspace_ships_every_fixture_under_its_sandbox_name():
    mapping = {w["src"]: w["dest"] for w in _eval_task().get("workspace", [])}
    for src in mapping:
        assert (_REPO_ROOT / src).exists(), src
    shipped = {
        str(p.relative_to(_REPO_ROOT)) for p in _WORKSPACE.rglob("*.txt")
    }
    assert shipped == set(mapping), shipped ^ set(mapping)
    # The grader's hashed paths are where the skill lands in the sandbox, and
    # each comes from the fixture the hash was taken from.
    for rel, src in _SKILL_SRC.items():
        assert mapping.get(str(src.relative_to(_REPO_ROOT))) == rel, rel


def test_eval_workspace_stays_out_of_graders():
    """skillgrade copies all of graders/ into the sandbox, so fixtures there
    would hand the model the compliant answer."""
    for w in _eval_task().get("workspace", []):
        assert not w["src"].startswith("graders/"), w["src"]


def test_keeps_old_guidance_rejects_a_clause_saying_the_old_token_stopped_working():
    """A clause that names the old filter only to say it is gone keeps nothing."""
    gate = "`name__like` was removed before 1.7. From 1.6: `name__contains`, required from 1.7."
    ok, msg = _mod.check_gate_keeps_old_guidance(_gate_report(gate), root=Path("."), **_KEEPS_OLD)
    assert not ok, msg


def test_keeps_old_guidance_matches_the_old_token_as_a_whole_word():
    gate = "Before 1.7: `name__likeness` still works. From 1.6: `name__contains`, required from 1.7."
    ok, msg = _mod.check_gate_keeps_old_guidance(_gate_report(gate), root=Path("."), **_KEEPS_OLD)
    assert not ok, msg


def _patch_report(deprecated: str, removed: str, gate: str) -> str:
    return (
        "### Finding 1\n\n- Repository: opsmill/infrahub\n- Severity: High\n"
        "- Affected: skills/acme-querying-inventory/rules/filters.md:9\n"
        f"- Deprecated in: {deprecated}\n- Removed in: {removed}\n"
        "- Verified in: infrahub-v1.12.1:backend/infrahub/graphql/filters.py\n"
        f"- Gate: {gate}\n"
    )


_PATCH = {
    "affected_path": "skills/acme-querying-inventory/rules/filters.md",
    "deprecated": "1.12.0",
    "removed": "1.12.1",
}
_PATCH_GATE = (
    "Infrahub 1.12.0 and later: use `name__contains`. It is required from 1.12.1. "
    "Before 1.12.0: `name__like` still works."
)


def test_gate_boundaries_tell_patch_releases_apart():
    """A deprecation in 1.12.0 and a removal in 1.12.1 are two boundaries."""
    good = _patch_report("infrahub-v1.12.0", "infrahub-v1.12.1", _PATCH_GATE)
    ok, msg = _mod.check_gate_boundaries(good, **_PATCH)
    assert ok, msg

    collapsed = _patch_report("infrahub-v1.12.0", "infrahub-v1.12.0", _PATCH_GATE)
    ok, msg = _mod.check_gate_boundaries(collapsed, **_PATCH)
    assert not ok
    assert "'Removed in'" in msg

    one_boundary = _patch_report(
        "infrahub-v1.12.0",
        "infrahub-v1.12.1",
        "Infrahub 1.12 and later: use `name__contains`. Before 1.12: `name__like` still works.",
    )
    ok, msg = _mod.check_gate_boundaries(one_boundary, **_PATCH)
    assert not ok, msg


def test_keeps_old_guidance_tells_patch_releases_apart():
    kwargs = {**_PATCH, "old_token": "name__like", "new_token": "name__contains"}
    ok, msg = _mod.check_gate_keeps_old_guidance(
        _patch_report("infrahub-v1.12.0", "infrahub-v1.12.1", _PATCH_GATE), **kwargs
    )
    assert ok, msg
    # The new filter starts at 1.12.1, so 1.12.0 has no guidance.
    gap = "From 1.12.1: `name__contains`. Before 1.12.0: `name__like` still works."
    ok, msg = _mod.check_gate_keeps_old_guidance(
        _patch_report("infrahub-v1.12.0", "infrahub-v1.12.1", gap), **kwargs
    )
    assert not ok, msg


def test_gate_boundaries_ignore_the_release_named_in_brackets():
    """The skill's SDK form names the Infrahub release that shipped it."""
    report = (_FIXTURES / "pass.txt").read_text().replace(
        "- Removed in: infrahub-v1.7.0",
        "- Removed in: infrahub-v1.7.0 (shipped with infrahub-sdk v1.30.0)",
    )
    ok, msg = _mod.check_gate_boundaries(
        report, affected_path=_KEEPS_OLD["affected_path"], deprecated="1.6", removed="1.7"
    )
    assert ok, msg


@pytest.mark.parametrize(
    ("verified", "ok"),
    [
        # A source file at the root of the repository.
        ("infrahub-v1.7.0:pyproject.toml", True),
        # A file name made of hex letters is not a commit.
        ("backend/deadbeef.py", False),
        ("backend/infrahub/deadbeef1.py", False),
        # A version alone is not a path.
        ("infrahub-v1.7.0", False),
    ],
)
def test_evidence_pinned_reads_the_commit_and_the_path_apart(verified, ok):
    report = (_FIXTURES / "pass.txt").read_text().replace(_VERIFIED, f"- Verified in: {verified}")
    passed, msg = _mod.check_evidence_pinned(report, start="1.6.0", end="1.7.0")
    assert passed is ok, msg


@pytest.mark.parametrize(
    ("location", "ok"),
    [
        ("rules/filters.md:9-13", True),
        ("rules/filters.md:9-999", False),
        ("rules/filters.md:0", False),
        ("rules/filters.md:13-9", False),
    ],
)
def test_affected_line_range_lies_inside_the_file(tmp_path, location, ok):
    report = _workspace(tmp_path, "pass")
    text = report.read_text().replace("rules/filters.md:9", location)
    passed, msg = _mod.check_affected_paths_exist(text, root=tmp_path)
    assert passed is ok, msg


def test_affected_path_stays_inside_the_workspace(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    report = _workspace(root, "pass")
    (tmp_path / "outside.md").write_text("one\ntwo\n")
    text = report.read_text().replace(
        "skills/acme-querying-inventory/rules/filters.md:9", "../outside.md:1"
    )
    ok, msg = _mod.check_affected_paths_exist(text, root=root)
    assert not ok
    assert "outside the workspace" in msg
