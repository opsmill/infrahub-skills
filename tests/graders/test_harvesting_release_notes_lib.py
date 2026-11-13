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


def test_violating_fixture_fails_on_the_gate_and_the_edit(tmp_path):
    result = run_checks(_task_checks(), _workspace(tmp_path, "fail"))
    failed = _failed(result)
    assert result["score"] < 1.0
    for name in ("gate-boundaries", "gate-keeps-old-guidance", "evidence-pinned", "skill-unchanged"):
        assert name in failed, failed


def test_near_miss_fails_only_on_gate_boundaries(tmp_path):
    result = run_checks(_task_checks(), _workspace(tmp_path, "fail-nearmiss"))
    assert _failed(result) == ["gate-boundaries"], result["checks"]


def _gate_report(gate: str) -> str:
    return (_FIXTURES / "pass.txt").read_text().replace(
        "- Gate: `name__contains` is available from Infrahub 1.6 and required from 1.7. "
        "Before 1.7: `name__like` still works.",
        f"- Gate: {gate}",
    )


_KEEPS_OLD = {
    "affected_path": "skills/acme-querying-inventory/rules/filters.md",
    "old_token": "name__like",
    "removed": "1.7",
    "deprecated": "1.6",
}


@pytest.mark.parametrize(
    "gate",
    [
        "Before 1.7: `name__like`. From 1.6: `name__contains`, required from 1.7.",
        "Infrahub 1.6 and earlier: `name__like` still works; `name__contains` from 1.6, required from 1.7.",
        "Up to 1.6: `name__like`. Available from 1.6 and required from 1.7: `name__contains`.",
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
        # The old filter appears only in the clause that removes it.
        "1.7 and later: `name__like` is removed, use `name__contains` (available from 1.6).",
        # The old guidance kept with no version at all.
        "From 1.6 use `name__contains`, required from 1.7. Earlier: `name__like`.",
    ],
)
def test_keeps_old_guidance_rejects_a_clause_that_stops_short(gate):
    ok, msg = _mod.check_gate_keeps_old_guidance(_gate_report(gate), root=Path("."), **_KEEPS_OLD)
    assert not ok, msg


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
