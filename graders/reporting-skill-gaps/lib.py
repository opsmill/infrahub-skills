"""Shared grader library for the infrahub-reporting-skill-gaps skill.

These graders read the model's drafted issue text from ``output.md`` and
check that the skill's rules were followed: corroboration was checked before
drafting, triage happened, the implicated artifact was cited, duplicates were
searched, evidence was redacted, and the review gate was shown before any
submission. Check functions take ``(text, **kwargs)`` and return
``(passed, message)``. Return shape matches sibling grader libs so skillgrade
ingests it identically.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

CheckResult = tuple[bool, str]
CheckFn = Callable[..., CheckResult]


def _normalized(text: str) -> str:
    """Lowercase and collapse whitespace so a multi-word phrase still
    matches when a model wraps its prose across a line break.
    """
    return re.sub(r"\s+", " ", text.lower())


def check_no_draft_on_single_session(text: str, **_: object) -> CheckResult:
    """Output does not draft a full issue from a single, uncorroborated session."""
    # Matches either level-2 title prefix. The tag used to be the single
    # literal `[skill-friction]`; Task 3 split it into `[skill-bug]` and
    # `[skill-feature]`, so both must be checked here or a drafted issue
    # with the newer tag would slip past this gate undetected.
    has_issue_title = re.search(r"\[skill-(?:bug|feature)\]", text) is not None
    # Match the template's "Proposed rule change" heading at any depth of two
    # or more `#` (the real template uses `##`; do not require the literal
    # title tag to have survived, since a paraphrased draft is still a
    # draft).
    has_proposed_rule_change = re.search(
        r"^#{2,}\s*Proposed rule change", text, re.IGNORECASE | re.MULTILINE
    ) is not None
    if has_issue_title or has_proposed_rule_change:
        hits = []
        if has_issue_title:
            hits.append("[skill-bug]/[skill-feature] title line")
        if has_proposed_rule_change:
            hits.append("Proposed rule change heading")
        return False, f"drafted issue content found: {', '.join(hits)}"
    return True, "no drafted issue title or proposed-rule-change section"


def check_records_observation(text: str, **_: object) -> CheckResult:
    """Output records the friction as an observation for future corroboration."""
    low = text.lower()
    if "notes.jsonl" in low:
        return True, "mentions notes.jsonl"
    if "observ" in low and ("record" in low or "note" in low or "logg" in low):
        return True, "states the observation was recorded"
    return False, "no mention of notes.jsonl or a recorded observation"


def check_states_gate_reason(text: str, **_: object) -> CheckResult:
    """Output ties the decision to stop back to the corroboration gate itself.

    A response that merely narrates "I have not filed this" says nothing
    about why. The eval prompt already tells the model not to run `gh`,
    so that phrasing appears regardless of whether the gate was correctly
    applied. This check instead looks for language that names the actual
    reason: only one session, no prior occurrence, not corroborated.
    """
    low = text.lower()
    patterns = (
        "only one session",
        "only one occurrence",
        "no prior occurrence",
        "first time seeing this",
        "first time i've seen this",
        "first time i have seen this",
        "not seen before",
        "haven't seen this before",
        "have not seen this before",
        "single occurrence",
        "single session",
        "one session isn't enough",
        "one session is not enough",
        "not enough to corroborate",
        "not corroborated",
        "not yet corroborated",
        "no corroboration",
        "no second session",
        "no second occurrence",
    )
    hits = [p for p in patterns if p in low]
    if hits:
        return True, f"ties the decision to the corroboration gate (matched: {hits[0]!r})"
    return False, "no phrase tying the decision to a single session / lack of corroboration"


_NEITHER_PATTERNS = (
    r"\bneither\b.{0,80}\b(?:skill defect|product defect)\b",
    r"\bclassif\w*\s*[:\-]?\s*neither\b",
    r"\bis neither\b",
)


def check_states_classification(text: str, **_: object) -> CheckResult:
    """Output names one of the three level-1 outcomes explicitly."""
    low = _normalized(text)
    if "skill defect" in low:
        return True, "names classification: skill defect"
    if "product defect" in low:
        return True, "names classification: product defect"
    if any(re.search(p, low) for p in _NEITHER_PATTERNS):
        return True, "names classification: neither"
    return False, (
        "no explicit 'skill defect' / 'product defect' / 'neither' "
        "classification found"
    )


_RULE_CHANGE_REASON_PATTERNS = (
    "rule change would have prevented",
    "a rule would have prevented",
    "better guidance would have prevented",
    "would not have prevented this",
    "would not have prevented the",
    "no rule change would have helped",
    "guidance was correct",
    "followed the skill correctly",
    "guidance was missing",
    "guidance was wrong",
    "guidance was unclear",
    "would a rule change have prevented",
    "rule change would prevent",
    "rule change would not have changed",
)


def check_justifies_classification(text: str, **_: object) -> CheckResult:
    """Output ties the level-1 classification to whether a rule change would
    have prevented the friction, not merely to how the classification felt.
    """
    low = _normalized(text)
    hits = [p for p in _RULE_CHANGE_REASON_PATTERNS if p in low]
    if hits:
        return True, (
            "ties classification to whether a rule change would have "
            f"prevented it (matched: {hits[0]!r})"
        )
    return False, (
        "no reasoning tied to whether a rule change would have prevented "
        "the friction"
    )


_NEGATION_WORDS = (
    "not",
    "isn't",
    "isnt",
    "never",
    "rather than",
    "as opposed to",
    "instead of",
)


def _term_is_negated(text: str, term: str) -> bool:
    """True when a negation word attaches to `term` within a few words.

    Catches both natural orders of contrastive phrasing alike: "not a bug,
    it's a feature" (negation precedes the rejected term) and "this is a
    bug, not a feature" (negation still precedes whichever term it
    rejects, just later in the sentence). Position in the sentence does
    not matter; only which term the negation word is actually attached to
    does.
    """
    alternation = "|".join(re.escape(w) for w in _NEGATION_WORDS)
    pattern = rf"(?:{alternation})\b(?:\s+\w+){{0,3}}\s+{term}\b"
    return re.search(pattern, text) is not None


def check_states_bug_or_feature(text: str, **_: object) -> CheckResult:
    """Output names the level-2 kind explicitly and uses the matching title
    prefix. `\\bbug\\b` does not match inside "debug" (the boundary before
    "b" fails when preceded by "de").

    Contrastive phrasing mentions both terms, in either order: "not a bug,
    it's a feature" or "this is a bug, not a feature" are equally natural,
    so position cannot resolve which term is the stated conclusion. This
    instead finds whichever term carries an attached negation ("not a
    bug", "rather than a feature") and treats the *other* term as the
    conclusion. When neither term is clearly negated, or both are, the
    check fails outright rather than guessing: a check that silently
    passes an unresolvable case is worse than one that says so. The tag
    brackets are stripped before this scan so a `[skill-bug]` tag's own
    substring "bug" is never counted as a prose mention.
    """
    low = _normalized(text)
    prose = re.sub(r"\[skill-(?:bug|feature)\]", " ", low)
    named_bug = re.search(r"\bbug\b", prose) is not None
    named_feature = re.search(r"\bfeature\b", prose) is not None
    has_bug_tag = "[skill-bug]" in text
    has_feature_tag = "[skill-feature]" in text

    if not (named_bug or named_feature):
        return False, "no explicit bug/feature classification named"
    if not (has_bug_tag or has_feature_tag):
        return False, "kind named but no [skill-bug]/[skill-feature] title prefix found"

    if named_bug and named_feature:
        bug_negated = _term_is_negated(prose, "bug")
        feature_negated = _term_is_negated(prose, "feature")
        if bug_negated and not feature_negated:
            stated = "feature"
        elif feature_negated and not bug_negated:
            stated = "bug"
        else:
            return False, (
                "both bug and feature are named but neither is clearly "
                "negated (or both are); cannot resolve which is the "
                "stated conclusion"
            )
    elif named_bug:
        stated = "bug"
    else:
        stated = "feature"

    if stated == "bug":
        if not has_bug_tag:
            return False, "stated kind is bug but title prefix uses [skill-feature]"
        return True, "names bug and uses matching [skill-bug] title prefix"
    if not has_feature_tag:
        return False, "stated kind is feature but title prefix uses [skill-bug]"
    return True, "names feature and uses matching [skill-feature] title prefix"


_COVERAGE_PATTERNS = (
    "already covers",
    "covers this topic",
    "covers the topic",
    "no rule covers",
    "no rule addresses",
    "no reference covers",
    "not covered by any rule",
    "no rule or reference covers",
    "does not cover this",
    "doesn't cover this",
    "skill already claims",
    "already claims to do this",
    "already claim this ground",
    "rule exists for this",
    "a rule covers",
    "no existing rule",
    "nothing in the skill covers",
    "the skill never claimed",
    "never claimed this ground",
    "does the skill already claim",
)

_SEVERITY_PATTERNS = (
    "round trips",
    "round-trips",
    "many attempts",
    "number of attempts",
    "user frustration",
    "how frustrating",
    "so many retries",
    "took so long",
    "took many tries",
    "severity of",
    "because it took",
    "given how much friction",
    "amount of friction",
    "how bad the friction felt",
)


def check_justifies_kind_by_coverage(text: str, **_: object) -> CheckResult:
    """Output ties bug-vs-feature to whether a rule already covers the
    topic, not to severity, round-trip count, or user frustration.

    Rejects the failure mode where a response reaches a defensible-looking
    answer ("this took eleven round trips so it is a bug") by reasoning
    about how bad the friction felt rather than about coverage.
    """
    low = _normalized(text)
    has_coverage = any(p in low for p in _COVERAGE_PATTERNS)

    severity_as_reason = False
    for pattern in _SEVERITY_PATTERNS:
        idx = low.find(pattern)
        if idx == -1:
            continue
        window = low[max(0, idx - 120) : idx + 120]
        if "bug" in window or "feature" in window or "because" in window or "so it is" in window or "so this is" in window:
            severity_as_reason = True
            break

    if severity_as_reason and not has_coverage:
        return False, "justifies kind by severity/round-trips rather than rule coverage"
    if has_coverage:
        return True, "ties kind to whether a rule or reference already covers the topic"
    return False, "no coverage-based justification found for the bug/feature kind"


_FEATURE_REASON_PATTERNS = (
    "no rule covers",
    "not covered by any rule",
    "no rule or reference covers",
    "skill's own files",
    "the skill did not cover",
    "skill never covered",
    "gap in the skill",
    "gap in coverage",
    "silent on this",
    "genuinely silent",
    "never claimed this ground",
    "the skill never claimed",
)

# workflow-bug-vs-feature.md's ordering caution: an escape that happened
# before the model read the skill's own rules is not a feature signal, it
# is the model skipping step 1 of the priority rule. A response that
# mentions an escape but explicitly disqualifies it this way is rule
# compliant and must not be penalized for failing to tie the (correctly
# disqualified) escape to a feature conclusion.
_ORDERING_DISQUALIFIED_PATTERNS = (
    "not a feature signal",
    "not feature evidence",
    "doesn't count as feature evidence",
    "does not count as feature evidence",
    "skipped step 1",
    "skipping step 1",
    "before checking the skill's own",
    "before checking whether the skill",
)
_ORDERING_DISQUALIFIED_REGEXES = (
    # Anchored to a word that names the disqualification itself ("escape",
    # or "happened before" describing the fetch's timing relative to
    # reading), not merely to "before" appearing near "skill's own"
    # anywhere in the text. A response that just narrates fetching before
    # opening the skill's own rules, without drawing the ordering
    # conclusion, must still fail: it never says the escape does not count.
    r"escape (?:happened|occurred)\b.{0,40}before",
    r"happened before\b.{0,40}(?:read|open|check)",
)


def check_cites_escape_as_feature_evidence(text: str, **_: object) -> CheckResult:
    """When the output shows a docs/llms.txt escape, it must either name
    that escape as the reason the kind is feature, or explicitly disqualify
    it under the ordering caution (the escape happened before the skill's
    own files were read, so it is a behavior defect, not a coverage gap).
    Vacuously passes when the output shows no escape at all, since the
    check does not apply then.
    """
    low = _normalized(text)
    has_escape = "llms.txt" in low or "docs.infrahub.app" in low
    if not has_escape:
        return True, "no docs/llms.txt escape evidence present; check not applicable"

    disqualified = any(p in low for p in _ORDERING_DISQUALIFIED_PATTERNS) or any(
        re.search(p, low) for p in _ORDERING_DISQUALIFIED_REGEXES
    )
    if disqualified:
        return True, (
            "escape present but correctly disqualified as feature evidence "
            "under the ordering caution"
        )

    tied_to_feature = "feature" in low and any(p in low for p in _FEATURE_REASON_PATTERNS)
    if tied_to_feature:
        return True, "names the docs/llms.txt escape as the reason for a feature classification"
    return False, (
        "docs/llms.txt escape present but not tied to a feature "
        "classification, and not disqualified by the ordering caution"
    )


def check_hands_off_to_reporting_issues(text: str, **_: object) -> CheckResult:
    """Output references infrahub-reporting-issues for the product-defect handoff."""
    if "infrahub-reporting-issues" in text:
        return True, "references infrahub-reporting-issues"
    return False, "no reference to infrahub-reporting-issues"


_NO_SKILLS_REPO_NEGATIONS = (
    "not",
    "instead of",
    "rather than",
    "never",
    "don't",
    "do not",
    "avoid",
    "without",
    "isn't",
    "won't",
)


def check_no_skills_issue_for_product_bug(text: str, **_: object) -> CheckResult:
    """Output drafts nothing against opsmill/infrahub-skills for a product bug.

    A mention of `opsmill/infrahub-skills` in a negated context ("handing
    off instead of filing against opsmill/infrahub-skills") is the correct,
    expected phrasing and must not fail this check; only an unnegated use as
    an actual filing target counts as a violation.
    """
    hits = []
    if "[skill-bug]" in text:
        hits.append("[skill-bug] title line")
    if "[skill-feature]" in text:
        hits.append("[skill-feature] title line")

    for match in re.finditer(r"opsmill/infrahub-skills", text):
        window = text[max(0, match.start() - 40) : match.start()].lower()
        if not any(neg in window for neg in _NO_SKILLS_REPO_NEGATIONS):
            hits.append("opsmill/infrahub-skills used as a filing target")
            break

    if hits:
        return False, f"found skills-repo issue content: {', '.join(hits)}"
    return True, "no skill-repo title tag and no opsmill/infrahub-skills filing target"


CHECKS: dict[str, CheckFn] = {
    "no-draft-on-single-session": check_no_draft_on_single_session,
    "records-observation": check_records_observation,
    "states-gate-reason": check_states_gate_reason,
    "states-classification": check_states_classification,
    "justifies-classification": check_justifies_classification,
    "states-bug-or-feature": check_states_bug_or_feature,
    "justifies-kind-by-coverage": check_justifies_kind_by_coverage,
    "cites-escape-as-feature-evidence": check_cites_escape_as_feature_evidence,
    "hands-off-to-reporting-issues": check_hands_off_to_reporting_issues,
    "no-skills-issue-for-product-bug": check_no_skills_issue_for_product_bug,
}

CheckSpec = str | tuple[str, dict]


def run_checks(check_specs: list[CheckSpec], output_path: Path) -> dict:
    """Run named checks against the model's drafted issue text; return skillgrade JSON."""
    text = output_path.read_text(errors="ignore") if output_path.exists() else ""
    entries: list[dict] = []
    passed_count = 0

    for spec in check_specs:
        name, kwargs = (spec if isinstance(spec, tuple) else (spec, {}))
        fn = CHECKS.get(name)
        if fn is None:
            entries.append({"name": name, "passed": False, "message": f"Unknown check: {name}"})
            continue
        try:
            ok, msg = fn(text, **kwargs)
        except Exception as exc:  # pragma: no cover, defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        display = name if not kwargs else f"{name}({','.join(f'{k}={v}' for k, v in kwargs.items())})"
        entries.append({"name": display, "passed": ok, "message": msg})

    total = len(check_specs)
    score = round(passed_count / total, 4) if total else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    details = (
        f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
        if failed else f"All {total} checks passed."
    )
    return {"score": score, "details": details, "checks": entries}


def main_cli() -> None:
    import sys
    if len(sys.argv) < 3:
        print("usage: python lib.py <output-file> <check-name> ...", file=sys.stderr)
        raise SystemExit(2)
    print(json.dumps(run_checks(list(sys.argv[2:]), Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    main_cli()
