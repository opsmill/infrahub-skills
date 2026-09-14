"""Tests for the audit-* evidence checks in graders/auditing-repo/lib.py.

These three checks exist because an audit can state something it never
established, and the finding reads identically either way. Each case below is
a findings payload a real audit can emit: the answer that did the work, the
same answer worded differently, the answer that skipped the work, and the
near-miss that carries the field the check looks for but fills it with the
inference the rule forbids.

The near-miss is the case that matters. A check that only asserts a field is
present reports the rule as covered while passing exactly the finding that
motivated it.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LIB_PATH = _REPO_ROOT / "graders" / "auditing-repo" / "lib.py"
_spec = importlib.util.spec_from_file_location("auditing_repo_evidence_lib", _LIB_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_checks = _mod.run_checks


def _score(tmp_path: Path, checks, payload) -> float:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    out = tmp_path / "output.json"
    out.write_text(raw, encoding="utf-8")
    return run_checks(checks, out)["score"]


# ---------------------------------------------------------------------------
# audit-sites-complete  (#123)
#
# The fixture repo references the denormalized attribute in four places. The
# fourth is reachable only by walking a double-quoted `{% import "..." %}`,
# which is the scan that silently under-reports when it matches one quote
# style.
# ---------------------------------------------------------------------------

SITES_RULE = "yagni-denormalized-vs-indirect-relationship"
ALL_FOUR = (
    "schemas/dcim.yml,templates/device_config.j2,"
    "templates/device_interfaces.j2,queries/device_info.gql"
)
SITES_CHECKS = [f"audit-sites-complete:{SITES_RULE}:{ALL_FOUR}"]


def _sites_finding(sites, **extra):
    finding = {
        "rule": SITES_RULE,
        "severity": "LOW",
        "ladder_step": 4,
        "file": "schemas/dcim.yml",
        "line": "42",
    }
    if sites is not None:
        finding["sites"] = sites
    finding.update(extra)
    return [finding]


def test_sites_complete_accepts_all_four_reference_sites(tmp_path):
    """The audit swept the repo and listed every site, including the imported one."""
    payload = _sites_finding([
        "schemas/dcim.yml:42",
        "templates/device_config.j2:15",
        "templates/device_interfaces.j2:8",
        "queries/device_info.gql:12",
    ])
    assert _score(tmp_path, SITES_CHECKS, payload) == 1.0


def test_sites_complete_accepts_bare_paths_in_any_order(tmp_path):
    """Same four sites, no line numbers, different order, a ./ prefix on one."""
    payload = _sites_finding([
        "queries/device_info.gql",
        "./templates/device_interfaces.j2",
        "schemas/dcim.yml",
        "templates/device_config.j2",
    ])
    assert _score(tmp_path, SITES_CHECKS, payload) == 1.0


def test_sites_complete_fails_when_finding_cites_only_its_own_file(tmp_path):
    """The defect: `file:line` stands in for the answer and no sweep was run."""
    payload = _sites_finding(None)
    assert _score(tmp_path, SITES_CHECKS, payload) == 0.0


def test_sites_complete_fails_the_partial_sweep_near_miss(tmp_path):
    """Near-miss: a populated `sites` list that stops at the obvious two.

    This is the finding that named two sites where a repo-wide grep found
    eight. It satisfies any check that merely asserts `sites` is present.
    """
    payload = _sites_finding([
        "schemas/dcim.yml:42",
        "templates/device_config.j2:15",
    ])
    assert _score(tmp_path, SITES_CHECKS, payload) == 0.0


def test_sites_complete_fails_when_an_unregistered_lookalike_is_cited(tmp_path):
    """The orphan template has the more canonical name; it is not the render site."""
    payload = _sites_finding([
        "schemas/dcim.yml:42",
        "templates/device.j2:15",
        "templates/device_interfaces.j2:8",
        "queries/device_info.gql:12",
    ])
    assert _score(tmp_path, SITES_CHECKS, payload) == 0.0


# ---------------------------------------------------------------------------
# audit-verified-against / audit-replacement-omits  (#124)
#
# `__gte` does not exist in the audited version. The audit must resolve the
# filter from that version's own models before recommending it.
# ---------------------------------------------------------------------------

SYNTAX_RULE = "yagni-redundant-check-that-graphql-can-answer"
SYNTAX_CHECKS = [
    f"audit-verified-against:{SYNTAX_RULE}",
    f"audit-replacement-omits:{SYNTAX_RULE}:__gte",
]


def _syntax_finding(replacement, verified_against=None):
    finding = {
        "rule": SYNTAX_RULE,
        "severity": "LOW",
        "ladder_step": 6,
        "file": "checks/check_interface_count.py",
        "line": "18",
        "replacement": replacement,
    }
    if verified_against is not None:
        finding["verified_against"] = verified_against
    return [finding]


def test_verified_syntax_accepts_a_filter_resolved_from_the_pinned_version(tmp_path):
    """The audit read the version's own filter generator and proposed what exists."""
    payload = _syntax_finding(
        "DcimInterface(role__values: [\"uplink\", \"peer\"]) { count }",
        "infrahub 1.11.1 attribute filter generator in the pinned image",
    )
    assert _score(tmp_path, SYNTAX_CHECKS, payload) == 1.0


def test_verified_syntax_accepts_an_unverifiable_proposal_that_says_so(tmp_path):
    """Cannot verify is a fine answer, as long as the finding says it and stops."""
    payload = _syntax_finding(
        "Keep the Python check; a server-side count filter could not be confirmed.",
        "not verified: the pinned image was unavailable, so no filter is proposed",
    )
    assert _score(tmp_path, SYNTAX_CHECKS, payload) == 1.0


def test_verified_syntax_fails_a_proposal_with_no_statement_of_verification(tmp_path):
    """The defect: a nonexistent filter asserted in the same voice as a real one."""
    payload = _syntax_finding("DcimInterface(count__gte: 48) { count }")
    assert _score(tmp_path, SYNTAX_CHECKS, payload) == 0.0


def test_verified_syntax_fails_the_same_form_as_the_sibling_near_miss(tmp_path):
    """Near-miss: `verified_against` is populated, with an inference in it.

    A sibling query demonstrating one filter is evidence for that filter. Both
    checks now catch this: the syntax check rejects the `__gte` it ships, and
    the verification check rejects the analogy it rests on. It scored 0.5 while
    the second was presence-only, which left the rule's "same form as the
    sibling is not verification" sentence resting on a fixture-specific token.
    """
    payload = _syntax_finding(
        "DcimInterface(count__gte: 48) { count }",
        "same form as the sibling query in queries/device_info.gql",
    )
    assert _score(tmp_path, SYNTAX_CHECKS, payload) == 0.0


# ---------------------------------------------------------------------------
# audit-extraction-feasibility  (#125)
#
# The three member kinds carry different relationship identifiers, so the
# parent edge cannot be hoisted and `clear` is not available.
# ---------------------------------------------------------------------------

GENERIC_RULE = "yagni-duplicate-shape-not-extracted-to-generic"
GENERIC_CHECKS = [
    f"audit-extraction-feasibility:{GENERIC_RULE}:blocked-differing-identifiers",
]


def _generic_finding(feasibility=None):
    finding = {
        "rule": GENERIC_RULE,
        "severity": "MEDIUM",
        "ladder_step": 2,
        "file": "schemas/dcim.yml",
        "line": "10",
    }
    if feasibility is not None:
        finding["feasibility"] = feasibility
    return [finding]


def test_feasibility_accepts_the_blocked_verdict(tmp_path):
    """The audit checked the identifiers and reported what it found."""
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding(
        "blocked-differing-identifiers")) == 1.0


def test_feasibility_accepts_the_blocked_verdict_with_surrounding_prose(tmp_path):
    """Same verdict, written as a sentence rather than a bare token."""
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding(
        "blocked-differing-identifiers: device_location, rack_location and "
        "circuit_site are three identifiers, and they are immutable once loaded"
    )) == 1.0


def test_feasibility_fails_when_the_field_is_absent(tmp_path):
    """The defect: an extraction proposed with no feasibility verdict at all."""
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding(None)) == 0.0


def test_feasibility_fails_the_unchecked_clear_near_miss(tmp_path):
    """Near-miss: `feasibility` is populated, and populated with `clear`.

    This is the finding that proposed what its own sibling finding forbade.
    """
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding("clear")) == 0.0


def test_feasibility_fails_the_unverified_default(tmp_path):
    """`clear (unverified)` is the honest default, not a verdict of feasible."""
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding(
        "clear (unverified)")) == 0.0


# ---------------------------------------------------------------------------
# The task graders themselves, against the four fixtures each.
#
# The checks above prove one assertion in isolation. These prove the bundle a
# real eval run scores, including the gate: without one, an answer that emits
# a well-formed finding and skips the evidence still clears the 0.8 threshold
# on the surrounding baseline checks.
# ---------------------------------------------------------------------------

def _grader(name: str):
    path = _REPO_ROOT / "graders" / "auditing-repo" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"grader_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _task_score(tmp_path: Path, grader_name: str, payload) -> float:
    mod = _grader(grader_name)
    out = tmp_path / "output.json"
    out.write_text(json.dumps(payload), encoding="utf-8")
    return run_checks(mod.CHECKS, out, mod.GATE_CHECKS)["score"]


REFERENCE_SITES_GRADER = "check_audit_reference_sites"
PROPOSED_SYNTAX_GRADER = "check_audit_proposed_syntax"
FEASIBILITY_GRADER = "check_audit_extraction_feasibility"


@pytest.mark.parametrize("sites,expected", [
    pytest.param([
        "schemas/dcim.yml:42",
        "templates/device_config.j2:15",
        "templates/device_interfaces.j2:8",
        "queries/device_info.gql:12",
    ], 1.0, id="compliant"),
    pytest.param([
        "queries/device_info.gql",
        "./templates/device_interfaces.j2",
        "schemas/dcim.yml",
        "templates/device_config.j2",
    ], 1.0, id="compliant-reworded"),
    pytest.param(None, 0.0, id="violating-no-sweep"),
    pytest.param([
        "schemas/dcim.yml:42",
        "templates/device.j2:15",
    ], 0.0, id="near-miss-partial-and-orphan"),
])
def test_reference_sites_task_grader(tmp_path, sites, expected):
    finding = {
        "rule": SITES_RULE,
        "severity": "LOW",
        "ladder_step": 4,
        "file": "schemas/dcim.yml",
        "line": "42",
    }
    if sites is not None:
        finding["sites"] = sites
    assert _task_score(tmp_path, REFERENCE_SITES_GRADER, [finding]) == expected


@pytest.mark.parametrize("replacement,verified,expected", [
    pytest.param(
        'DcimInterface(role__values: ["uplink", "peer"]) { count }',
        "infrahub 1.11.1 attribute filter generator in the pinned image",
        1.0, id="compliant"),
    pytest.param(
        "Keep the Python check; no server-side count filter exists in 1.11.1.",
        "read the filter generator off the pinned image; it emits no range filter",
        1.0, id="compliant-reworded"),
    pytest.param(
        "DcimInterface(count__gte: 48) { count }", None,
        0.0, id="violating-unverified-and-nonexistent"),
    pytest.param(
        "DcimInterface(count__gte: 48) { count }",
        "same form as the sibling query in queries/device_info.gql",
        0.0, id="near-miss-sibling-inference"),
])
def test_proposed_syntax_task_grader(tmp_path, replacement, verified, expected):
    finding = {
        "rule": SYNTAX_RULE,
        "severity": "LOW",
        "ladder_step": 6,
        "file": "checks/check_interface_count.py",
        "line": "18",
        "replacement": replacement,
    }
    if verified is not None:
        finding["verified_against"] = verified
    assert _task_score(tmp_path, PROPOSED_SYNTAX_GRADER, [finding]) == expected


@pytest.mark.parametrize("feasibility,sites,expected", [
    pytest.param(
        "blocked-differing-identifiers",
        ["schemas/dcim.yml", "schemas/circuit.yml", "schemas/rack.yml"],
        1.0, id="compliant"),
    pytest.param(
        "blocked-differing-identifiers: three identifiers, immutable once loaded",
        ["schemas/rack.yml:4", "schemas/dcim.yml:10", "schemas/circuit.yml:7"],
        1.0, id="compliant-reworded"),
    pytest.param(
        None,
        ["schemas/dcim.yml", "schemas/circuit.yml"],
        0.0, id="violating-no-verdict"),
    pytest.param(
        "clear",
        ["schemas/dcim.yml", "schemas/circuit.yml"],
        0.0, id="near-miss-unchecked-clear"),
])
def test_extraction_feasibility_task_grader(tmp_path, feasibility, sites, expected):
    finding = {
        "rule": GENERIC_RULE,
        "severity": "MEDIUM",
        "ladder_step": 2,
        "file": "schemas/dcim.yml",
        "line": "10",
        "sites": sites,
    }
    if feasibility is not None:
        finding["feasibility"] = feasibility
    assert _task_score(tmp_path, FEASIBILITY_GRADER, [finding]) == expected


# ---------------------------------------------------------------------------
# The severity cap and INFO.
#
# The cap bounds severity from above, so it only ever needs to reject CRITICAL
# and HIGH. INFO is the skill's own legend entry for an informational
# observation (`audit-procedure.md` severity legend), it sits below MEDIUM, and
# `audit-procedure.md` directs an INFO finding in its own right, so the cap has
# to admit it. Rejecting INFO was the cap misreading its own name.
#
# Note this is not about downgrading: `audit-verifies-proposed-syntax` Check 6
# forbids lowering severity to express low confidence. Severity belongs to the
# rule; what weakens is the claim.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("severity,expected", [
    pytest.param("MEDIUM", True, id="medium-allowed"),
    pytest.param("LOW", True, id="low-allowed"),
    pytest.param("INFO", True, id="info-is-below-medium"),
    pytest.param("HIGH", False, id="high-is-above-the-cap"),
    pytest.param("CRITICAL", False, id="critical-is-above-the-cap"),
    pytest.param("", False, id="missing-severity-still-fails"),
])
def test_severity_cap_admits_info(tmp_path, severity, expected):
    payload = [{
        "rule": SYNTAX_RULE,
        "severity": severity,
        "ladder_step": 6,
        "file": "checks/check_interface_count.py",
    }]
    passed = _score(tmp_path, ["yagni-no-above-medium"], payload) == 1.0
    assert passed is expected


def test_feasibility_rejects_the_outcome_used_as_a_verdict(tmp_path):
    """`attributes-only` describes the reduction, not why it was forced.

    An earlier draft of the rule listed it as a verdict alongside the
    `blocked-` reasons, which made two labels correct for the same finding.
    The verdict names the blocker; the reduction belongs in the replacement.
    """
    assert _score(tmp_path, GENERIC_CHECKS, _generic_finding(
        "attributes-only")) == 0.0


# ---------------------------------------------------------------------------
# Ladder ordering across mixed ladder_step types.
#
# Models emit the step as an int or as a string interchangeably.
# check_yagni_finding_ladder_step already normalises with str() for that
# reason; the ordering check did not, so a correctly sorted report died in
# the comparison and surfaced as "Error running check".
# ---------------------------------------------------------------------------

def _ordered(*steps):
    return [
        {"rule": f"yagni-r{i}", "severity": "LOW", "ladder_step": s,
         "file": f"{i}.yml"}
        for i, s in enumerate(steps)
    ]


@pytest.mark.parametrize("steps,expected", [
    pytest.param((1, 2, 3), 1.0, id="ints-ascending"),
    pytest.param(("1", "2", "3"), 1.0, id="strings-ascending"),
    pytest.param((1, "2", 3), 1.0, id="mixed-types-ascending"),
    pytest.param((2, "10"), 1.0, id="mixed-types-not-sorted-lexically"),
    pytest.param((3, "2", 1), 0.0, id="mixed-types-descending-still-fails"),
])
def test_ladder_ordering_normalises_step_types(tmp_path, steps, expected):
    assert _score(tmp_path, ["yagni-findings-sorted"], _ordered(*steps)) == expected


# ---------------------------------------------------------------------------
# Both directions of the two evidence gates.
#
# A gate zeroes the task, so a gate that grades the wrong thing is expensive in
# both directions: it fails an answer that did the work, and it passes one that
# did not.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict,expected", [
    pytest.param("blocked-differing-identifiers", 1.0, id="blocker-identifiers"),
    pytest.param("blocked-differing-peers", 1.0, id="blocker-peers"),
    pytest.param(
        "blocked-differing-peers: CircuitEndpoint peers LocationBuilding where "
        "Device and Rack peer LocationSite",
        1.0, id="blocker-peers-with-prose"),
    pytest.param("clear", 0.0, id="unchecked-clear-still-fails"),
    pytest.param("clear (unverified)", 0.0, id="default-still-fails"),
])
def test_feasibility_accepts_either_true_blocker(tmp_path, verdict, expected):
    """The fixture trips two blockers, so either verdict is a correct read.

    Three identifiers (`device__location`, `rack__location`, `circuit__site`)
    and two peer kinds (`LocationSite` twice, `LocationBuilding` once). The
    rule states the two as equal blockers and gives no precedence. Pinning one
    zeroed an audit that named the other.
    """
    finding = {
        "rule": GENERIC_RULE,
        "severity": "MEDIUM",
        "ladder_step": 2,
        "file": "schemas/dcim.yml",
        "sites": ["schemas/dcim.yml", "schemas/rack.yml", "schemas/circuit.yml"],
        "feasibility": verdict,
    }
    assert _task_score(tmp_path, FEASIBILITY_GRADER, [finding]) == expected


def test_replacement_omits_inspects_every_finding_for_the_rule(tmp_path):
    """A clean leading finding must not launder a later one.

    An audit may emit one finding per offending file. Grading only the first
    match let a second finding carry `__gte` — the syntax the audited version
    does not implement — through a gate check at a full 1.0.
    """
    def _f(path, replacement):
        return {
            "rule": SYNTAX_RULE,
            "severity": "LOW",
            "ladder_step": 6,
            "file": path,
            "verified_against": "attribute filter generator, infrahub 1.11.1",
            "replacement": replacement,
        }

    clean = _f("checks/a.py", "Keep the Python check.")
    dirty = _f("checks/b.py", "DcimInterface(count__gte: 48) { count }")

    assert _task_score(tmp_path, PROPOSED_SYNTAX_GRADER, [clean, dirty]) == 0.0
    assert _task_score(tmp_path, PROPOSED_SYNTAX_GRADER, [dirty, clean]) == 0.0
    assert _task_score(tmp_path, PROPOSED_SYNTAX_GRADER, [clean, clean]) == 1.0


# ---------------------------------------------------------------------------
# The unverified default must not satisfy the verified verdict.
#
# `_verdict` took the leading token, so "clear (unverified)" reduced to
# "clear". The whole feasibility gate is built on that distinction: the
# default is what an implementer must re-derive, and `clear` is the promise
# that someone already did.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("feasibility,expected_verdict,should_pass", [
    pytest.param("clear", "clear", True, id="verified-clear-matches-clear"),
    pytest.param("clear (unverified)", "clear", False, id="default-is-not-clear"),
    pytest.param("clear(unverified)", "clear", False, id="default-without-space"),
    pytest.param("clear - unverified", "clear", False, id="default-with-dash"),
    pytest.param("clear (unverified)", "clear (unverified)", True, id="default-matches-itself"),
    pytest.param(
        "clear: identifiers, peers and hoisted settings all checked",
        "clear", True, id="verified-clear-may-explain-itself"),
])
def test_feasibility_separates_clear_from_the_unverified_default(
    tmp_path, feasibility, expected_verdict, should_pass
):
    checks = [f"audit-extraction-feasibility:{GENERIC_RULE}:{expected_verdict}"]
    scored = _score(tmp_path, checks, _generic_finding(feasibility)) == 1.0
    assert scored is should_pass


# ---------------------------------------------------------------------------
# "Same form as the sibling" is not verification.
#
# The rule says so in Check 3, but the check only asserted the field was
# non-empty, so the sentence had no test that could fail. The near-miss
# fixture scored 0.5 purely on the companion __gte check, which is specific
# to that fixture and would not carry to any other task.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stated,should_pass", [
    pytest.param(
        "attribute filter generator, infrahub 1.11.1 pinned image",
        True, id="names-the-artifact-and-version"),
    pytest.param(
        "read the filter generator off the pinned image; it emits no range filter",
        True, id="names-what-was-read"),
    pytest.param(
        "not verified: the pinned image was unavailable",
        True, id="declares-non-verification"),
    pytest.param(
        "same form as the sibling query in queries/device_info.gql",
        False, id="sibling-analogy-is-not-evidence"),
    pytest.param(
        "the same form another query already uses",
        False, id="another-query-analogy"),
    pytest.param(
        "by analogy with the existing dropdown filter",
        False, id="explicit-analogy"),
])
def test_verified_against_rejects_an_in_repo_analogy(tmp_path, stated, should_pass):
    checks = [f"audit-verified-against:{SYNTAX_RULE}"]
    payload = _syntax_finding("DcimInterface(role__values: [\"uplink\"]) { count }", stated)
    scored = _score(tmp_path, checks, payload) == 1.0
    assert scored is should_pass


@pytest.mark.parametrize("stated,should_pass", [
    pytest.param(
        "the sibling query demonstrates only the singular filter, so it is not "
        "evidence; not verified against the pinned image",
        True, id="naming-the-sibling-to-reject-it-is-not-relying-on-it"),
    pytest.param(
        "could not verify: the image was unavailable, and the same form as the "
        "sibling query is not evidence",
        True, id="explicit-non-verification-outranks-a-quoted-marker"),
    pytest.param(
        "same form as the sibling query in queries/device_info.gql",
        False, id="still-fails-when-the-analogy-is-the-whole-evidence"),
])
def test_verified_against_allows_naming_an_analogy_in_order_to_reject_it(
    tmp_path, stated, should_pass
):
    """Matching the bare word `sibling` failed a correct answer.

    An audit that explains why the sibling proves nothing is doing exactly
    what Check 3 asks. Only a statement that *rests* on the analogy should
    fail, and an explicit declaration of non-verification outranks the
    marker entirely.
    """
    checks = [f"audit-verified-against:{SYNTAX_RULE}"]
    payload = _syntax_finding("Keep the Python check.", stated)
    assert (_score(tmp_path, checks, payload) == 1.0) is should_pass
