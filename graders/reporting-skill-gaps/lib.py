"""Shared grader library for the infrahub-reporting-skill-gaps skill.

These graders read the model's drafted issue text from ``output.md`` and
check that the skill's rules were followed: the tracker was searched before
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


# Level-2 title tag. It has moved four times: `[skill-friction]` first,
# then `[skill-bug]`/`[skill-feature]` once level-2 kind splitting shipped,
# then a bare `bug:`/`feat:` line prefix once filing moved to
# infrahub-reporting-issues, then a bare `docs:` sat between them once
# "no rule covers it" split into feature (a docs escape resolved the
# problem) and docs gap (the escape still failed), and now the docs-gap
# tag is `bug(docs):` instead of `docs:`, because a docs gap routes to
# opsmill/infrahub (Infrahub's docs live there, not in the skills repo)
# and that repo's own issue convention already uses a bare `Docs:` prefix
# for something else entirely (an area label on an ordinary bug/feature
# title, per infrahub-reporting-issues' shared convention); `bug(docs):`
# avoids colliding with that unrelated meaning. `bug\(docs\)` is listed
# before the bare `bug` alternative so the parenthesized form is tried
# first, though regex backtracking would find it either way. Anchored to
# the start of a markdown line (optionally after heading hashes or a
# bold-open marker) so ordinary prose like "there's a bug: the counter
# increments twice" does not false-match; a real title occupies its own
# line.
_TITLE_TAG_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(bug\(docs\)|bug|feat):\s*\S",
    re.IGNORECASE | re.MULTILINE,
)

# The tracker search the skill runs at step 2. `check_no_direct_filing`
# shares this pattern so the two checks cannot drift into disagreeing
# about whether narrating this command is compliant: it is required here
# and explicitly allowed there, unlike `gh issue create`/`gh issue
# comment`, which remain the sibling skill's alone.
_TRACKER_SEARCH_CMD_RE = re.compile(r"gh\s+search\s+issues", re.IGNORECASE)

_TRACKER_SEARCH_VERBS = ("search", "check", "look(?:ed|ing)\\s+for", "quer")
_TRACKER_TARGETS = (
    "opsmill/infrahub-skills", "the tracker", "existing issue", "open issue",
)

# Verb and target within a sentence's worth of characters, in either
# order. One precompiled alternation rather than a verb x target loop:
# the loop rebuilt up to 96 interpolated patterns per call and, worse,
# could not match "checked the tracker" without a fused verb entry.
_TRACKER_SEARCH_RE = re.compile(
    "(?:(?:{v}).{{0,120}}(?:{t}))|(?:(?:{t}).{{0,120}}(?:{v}))".format(
        v="|".join(_TRACKER_SEARCH_VERBS),
        t="|".join(re.escape(t) for t in _TRACKER_TARGETS),
    ),
    re.IGNORECASE,
)

_COMMENT_TERMS = (
    "comment on", "add a comment", "adding a comment", "drafted a comment",
    "draft a comment", "gh issue comment", "comment rather than",
    "comment instead of",
)


def check_searches_tracker_first(text: str, **_: object) -> CheckResult:
    """Output searched opsmill/infrahub-skills before drafting anything.

    The tracker, not the local machine, is the shared record of whether a
    friction has been seen before; see ``workflow-tracker-first.md``. A
    report drafted without it either duplicates an open issue or discards
    the one place a second observer would have found it.

    Naming the repo alone is not enough: the skill's own handoff prose
    mentions ``opsmill/infrahub-skills`` as the *target* repo in every
    report, so that string appears whether or not a search happened. A
    search verb must appear near it, in either order.

    Stems only in the verb list: matching is unanchored substring, so
    ``search`` already subsumes ``searched``/``searching``, and listing
    both would be dead entries that read as meaningful. ``check`` is a
    stem too, which is what makes the common "I checked the tracker"
    phrasing match without needing a fused verb+target entry.
    """
    if _TRACKER_SEARCH_CMD_RE.search(text):
        return True, "shows the gh search issues invocation"
    hit = _TRACKER_SEARCH_RE.search(_normalized(text))
    if hit:
        return True, f"states the tracker was searched (matched: {hit.group(0)[:60]!r})"
    return False, "no statement that the tracker was searched before drafting"


_CONFIDENCE_LABELS: dict[str, tuple[str, ...]] = {
    "recurring": (
        "recurring",
        "happened before",
        "seen this before",
        "second session",
        "second occurrence",
    ),
    "unconfirmed": (
        "unconfirmed",
        "single observation",
        "single sighting",
        "first sighting",
        "only one occurrence",
    ),
}

# The template ships `**Confidence**: [recurring | unconfirmed single
# observation]`, which contains phrases from *both* label sets. An
# unfilled placeholder is not a labelled report, so it must fail rather
# than satisfy the check by accident.
_UNFILLED_CONFIDENCE_RE = re.compile(
    r"confidence\W{0,4}\[[^\]]*\|", re.IGNORECASE
)


def check_marks_confidence(text: str, expected: str | None = None, **_: object) -> CheckResult:
    """Output labels how strong the evidence is, rather than hiding it.

    Replaces the old corroboration gate, which suppressed first sightings
    entirely. Suppression is worse than a thin issue: an observation that
    is never written down cannot be recovered, and the second observer on
    another machine sees a first sighting too. The report is always
    produced; what changes is the label it carries.

    ``expected`` names the label the scenario calls for, following the
    ``expected_kind`` precedent in ``check_states_bug_or_feature``: a
    report that confidently claims ``recurring`` on a first sighting is
    internally consistent and wrong, which is exactly the failure a
    label-agnostic check cannot see.
    """
    low = _normalized(text)
    if _UNFILLED_CONFIDENCE_RE.search(low):
        return False, "confidence line is still an unfilled template placeholder"
    found = {
        label: next((p for p in phrases if p in low), None)
        for label, phrases in _CONFIDENCE_LABELS.items()
    }
    hits = {label: p for label, p in found.items() if p is not None}
    if not hits:
        return False, "no confidence label (neither recurring nor unconfirmed) in the report"
    if expected is None:
        label, phrase = next(iter(hits.items()))
        return True, f"labelled {label} (matched: {phrase!r})"
    if expected not in hits:
        return False, (
            f"expected a {expected!r} label; found {sorted(hits) or 'none'}"
        )
    return True, f"labelled {expected} (matched: {hits[expected]!r})"


def check_comments_not_duplicates(text: str, **_: object) -> CheckResult:
    """When the tracker already covers the friction, output drafts a comment.

    A second issue splits the evidence across two threads and buries the
    corroboration a maintainer needs. The comment is the more valuable
    artifact, so a drafted title here is a failure even though a title is
    correct in every no-match scenario.

    Tests the proposed-rule-change heading as well as the title tag: a
    paraphrased draft that loses the tag but keeps the section is still a
    second issue, which is the duplicate this check exists to catch.
    """
    drafted = []
    if _TITLE_TAG_RE.search(text):
        drafted.append("bug:/feat:/bug(docs): title line")
    if _PROPOSED_CHANGE_HEADING_RE.search(text):
        drafted.append("Proposed rule change heading")
    if drafted:
        return False, (
            f"drafted new-issue content despite an existing issue covering the "
            f"friction ({', '.join(drafted)}); a comment was expected"
        )
    hit = next((p for p in _COMMENT_TERMS if p in _normalized(text)), None)
    if hit:
        return True, f"drafts a comment on the existing issue (matched: {hit!r})"
    return False, "no drafted comment on the existing issue, and no new title either"


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


# Each level-2 kind, in the order the classification table lists them:
# (prose label, title-tag value, detection regex, negation-search term).
# "docs gap" is matched as the two-word phrase, never the bare word "docs":
# "docs" alone appears constantly in compliant prose ("docs.infrahub.app",
# "the docs page", "fetched the docs") for reasons that have nothing to do
# with stating the kind, so a bare-word match would false-positive on
# almost every response that also discusses a feature or docs-gap escape.
# The negation-search term for "docs gap" uses `\s+` between the two words
# so it still matches if a line wrap inserts a newline between them. The
# docs-gap tag value is `bug(docs)`, not `docs`, matching the routing fix:
# a docs gap files against opsmill/infrahub under a title that reads
# `bug(docs): <summary>`.
_KIND_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("bug", "bug", r"\bbug\b", "bug"),
    ("feature", "feat", r"\bfeature\b", "feature"),
    ("docs gap", "bug(docs)", r"\bdocs\s+gap\b", r"docs\s+gap"),
)
_KIND_TAG_BY_NAME = {name: tag for name, tag, _, _ in _KIND_SPECS}
_VALID_EXPECTED_KINDS = frozenset(name for name, _, _, _ in _KIND_SPECS)


def check_states_bug_or_feature(
    text: str, *, expected_kind: str | None = None, **_: object
) -> CheckResult:
    """Output names the level-2 kind explicitly (bug, feature, or docs gap)
    and uses the matching title prefix. `\\bbug\\b` does not match inside
    "debug" (the boundary before "b" fails when preceded by "de").

    Contrastive phrasing can name two or all three terms, in any order:
    "not a bug, it's a feature", "this is a bug, not a feature", "not a
    bug and not a feature, it is a docs gap", "it's a docs gap, not a bug,
    not a feature" are all equally natural, so position cannot resolve
    which term is the stated conclusion. This instead finds which named
    terms carry an attached negation ("not a bug", "rather than a
    feature") and treats the conclusion as whichever named term is the
    sole one *without* a negation attached: with two terms named, exactly
    one of them must be negated; with three, exactly two. Any other split
    (zero negated when two are named; anything other than exactly two
    negated when three are named) is unresolvable and the check fails
    outright rather than guessing: a check that silently passes an
    unresolvable case is worse than one that says so.

    The title tag itself is stripped before this scan (using a
    real-newline-preserving lowercase, not `_normalized`, so the
    line-anchored strip actually lines up) so a `bug:` title's own
    substring "bug" is never counted as a prose mention; a `feat:` tag
    never contains the word "feature" and a `bug(docs):` tag never
    contains "docs gap", but the substitution strips all three prefixes
    for symmetry.

    `expected_kind`, when given (one of "bug", "feature", "docs gap";
    see `_VALID_EXPECTED_KINDS`), is the kind this scenario's own
    evidence actually supports, independent of whatever the drafted
    output claims. Without it, this check only verifies *internal*
    consistency: that the title tag agrees with the prose conclusion.
    That is not the same as being *right*: a response that misclassifies
    a scenario but stays internally consistent (tags itself `feat:` and
    says "feature" throughout, when the evidence is a docs gap) passed
    this check with a perfect score before `expected_kind` existed. Each
    level-2 eval task now passes its own scenario's correct kind here,
    so an internally-consistent but wrong answer is caught instead of
    scoring full marks. A typo in `expected_kind` itself (a label not in
    `_VALID_EXPECTED_KINDS`) raises rather than silently comparing
    against a value `stated` can never equal, which would otherwise fail
    every draft for this scenario without ever saying why: a caller-side
    bug dressed up as a model-side one.
    """
    if expected_kind is not None and expected_kind not in _VALID_EXPECTED_KINDS:
        raise ValueError(
            f"expected_kind={expected_kind!r} is not one of "
            f"{sorted(_VALID_EXPECTED_KINDS)}"
        )
    low = text.lower()
    tag_match = _TITLE_TAG_RE.search(text)
    tag_value = tag_match.group(1).lower() if tag_match else None

    prose = re.sub(
        r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:bug\(docs\)|bug|feat):\s*",
        " ",
        low,
        flags=re.MULTILINE,
    )

    named = [name for name, _, pattern, _ in _KIND_SPECS if re.search(pattern, prose)]

    if not named:
        return False, "no explicit bug/feature/docs gap classification named"
    if tag_value not in _KIND_TAG_BY_NAME.values():
        return False, "kind named but no bug:/feat:/bug(docs): title prefix found"

    if len(named) == 1:
        stated = named[0]
    else:
        term_by_name = {name: term for name, _, _, term in _KIND_SPECS}
        negated = {name: _term_is_negated(prose, term_by_name[name]) for name in named}
        unnegated = [name for name in named if not negated[name]]
        if len(unnegated) != 1:
            return False, (
                f"{', '.join(named)} are all named but the negation pattern "
                "does not resolve to exactly one stated conclusion"
            )
        stated = unnegated[0]

    expected_tag = _KIND_TAG_BY_NAME[stated]
    if tag_value != expected_tag:
        return False, (
            f"stated kind is {stated} but title prefix uses {tag_value}:"
        )

    if expected_kind is not None and stated != expected_kind:
        return False, (
            f"stated kind is {stated} (title prefix and prose agree with "
            f"each other), but this scenario's evidence supports "
            f"{expected_kind}"
        )
    return True, f"names {stated} and uses matching {expected_tag}: title prefix"


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


# Whether a docs escape (llms.txt or a docs.infrahub.app page reached
# through it) resolved the problem or not. This is the sentence the
# feature/docs-gap split rests on: "no rule covers it" is common to both,
# and only the post-escape outcome tells them apart. Kept broad but
# distinct from each other (a sample matching both is treated as
# self-contradictory by check_cites_escape_outcome below, not silently
# resolved either way).
_ESCAPE_RESOLVED_PATTERNS = (
    "found the answer",
    "which answered it",
    "that answered it",
    "the page answered",
    "answered the question",
    "which resolved the problem",
    "that resolved the problem",
    "which resolved this",
    "that resolved this",
    "worked after reading",
    "succeeded after",
    "which worked on the first try",
    "and it worked",
)
_ESCAPE_FAILED_PATTERNS = (
    "still failed",
    "still could not",
    "still couldn't",
    "did not address",
    "didn't address",
    "does not address",
    "doesn't address",
    "did not answer",
    "didn't answer",
    "does not answer",
    "doesn't answer",
    "no answer there either",
    "did not address the problem",
    "remained unresolved",
    "still unresolved",
    "did not resolve",
    "didn't resolve",
    "did not help",
    "didn't help",
    "page did not cover",
    "page didn't cover",
    "page did not address",
)


def check_justifies_kind_by_coverage(text: str, **_: object) -> CheckResult:
    """Output ties bug-vs-feature-vs-docs-gap to whether a rule already
    covers the topic, not to severity, round-trip count, or user
    frustration.

    Rejects the failure mode where a response reaches a defensible-looking
    answer ("this took eleven round trips so it is a bug") by reasoning
    about how bad the friction felt rather than about coverage.

    For a `bug(docs):` classification, coverage alone ("no rule covers this")
    is necessary but not sufficient: a feature draft says exactly the same
    thing about coverage, and the only sentence that tells the two apart
    is whether the docs escape resolved the problem or not. So a docs-gap
    draft must also state that the escape failed; coverage language
    without that outcome is treated the same as no justification at all.
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

    tag_match = _TITLE_TAG_RE.search(text)
    is_docs = bool(tag_match and tag_match.group(1).lower() == "bug(docs)")
    if is_docs:
        has_failed_outcome = any(p in low for p in _ESCAPE_FAILED_PATTERNS)
        if has_coverage and has_failed_outcome:
            return True, (
                "ties docs-gap kind to coverage plus the post-escape "
                "failure outcome"
            )
        if has_coverage and not has_failed_outcome:
            return False, (
                "docs-gap kind justified by coverage alone; missing the "
                "post-escape failure outcome that distinguishes it from "
                "a feature"
            )
        return False, "no coverage-based justification found for the docs-gap kind"

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


def check_cites_escape_outcome(text: str, **_: object) -> CheckResult:
    """When the evidence shows a docs/llms.txt escape, output states
    whether that escape resolved the problem.

    This is the sentence the whole feature/docs-gap split rests on: an
    escape alone only establishes that the skill's own material was
    checked and found silent. Whether the outcome is feature or docs gap
    depends entirely on what happened after the fetch, and this check
    exists to catch a draft that narrates the escape but never says which
    way it landed. Disqualified under the ordering caution the same way
    `cites_escape_as_feature_evidence` is: an escape that happened before
    the skill's own rules were read is a behavior defect, not evidence of
    either outcome, so its resolution status is moot and this check does
    not require one. Vacuously passes when no escape is present at all.
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
            "escape present but disqualified under the ordering caution; "
            "outcome not required"
        )

    resolved = any(p in low for p in _ESCAPE_RESOLVED_PATTERNS)
    failed = any(p in low for p in _ESCAPE_FAILED_PATTERNS)
    if resolved and failed:
        return False, "escape outcome contradicts itself: both resolved and failed language present"
    if resolved:
        return True, "states the escape resolved the problem"
    if failed:
        return True, "states the escape did not resolve the problem"
    return False, (
        "docs/llms.txt escape present but no statement of whether it "
        "resolved the problem"
    )


# The settled-behavior gate: a bug(docs): issue asks an Infrahub
# maintainer to write down an answer, so it is only actionable when an
# answer already exists to write down. When the topic itself is still
# being designed, or is deliberately left undocumented, there is nothing
# to document yet, and the correct move is to explain which behavior is
# unsettled and stop, rather than file a request nobody can fulfill. This
# is the one place the workflow stops without producing a report; it is
# not a confidence question, which `check_marks_confidence` answers with
# a label rather than with silence.
_UNSETTLED_GATE_REASON_PATTERNS = (
    "nothing to document yet",
    "nothing yet to document",
    "still being defined",
    "still being designed",
    "still under active design",
    "still under design",
    "still evolving",
    "still in flux",
    "still changing",
    "not finalized",
    "not yet finalized",
    "shape not finalized",
    "subject to change",
    "deliberately undocumented",
    "intentionally undocumented",
    "not yet settled",
    "behavior is not settled",
    "behaviour is not settled",
    "no settled behavior to document",
    "no settled behaviour to document",
    "not settled enough to document",
    "nothing settled to document",
    "not stable enough to document",
    "settled-behavior gate",
    "settled-behaviour gate",
)


def check_no_docs_gap_when_unsettled(text: str, **_: object) -> CheckResult:
    """Output does not draft *any* level-2 issue (or its Proposed rule
    change section) when the underlying behavior is still being designed
    or is deliberately undocumented by design.

    Uses a strict title-tag test: any `_TITLE_TAG_RE` match counts as a
    violation, not just `bug(docs):`. An earlier version of
    this check only flagged `bug(docs):`, which meant a `feat:` (or
    `bug:`) title drafted for the exact same unsettled scenario sailed
    through as "correctly withheld", satisfying the reason-phrase branch
    on the scenario's own wording while a full draft sat right there.
    That is wrong for every kind, not just docs gap: when the escape
    happened and failed, the three-way table already says docs gap
    before the gate is even reached, so a `feat:`/`bug:` draft of the
    same friction is simply a wrong classification wearing a different
    tag, not a compliant alternative. In an unsettled scenario, no
    level-2 draft of any kind is correct; only "explain why and stop"
    is. This is the one place the workflow stops without producing a
    report, and it is not a confidence question: `check_marks_confidence`
    answers those with a label rather than with silence. Here there is no
    stable behavior to document at all. A response that correctly
    withholds the draft must still say why, rather than a bare "not
    filing this."
    """
    has_tag = _TITLE_TAG_RE.search(text) is not None
    has_proposed_rule_change = _PROPOSED_CHANGE_HEADING_RE.search(text) is not None
    if has_tag or has_proposed_rule_change:
        hits = []
        if has_tag:
            hits.append("bug:/feat:/bug(docs): title line")
        if has_proposed_rule_change:
            hits.append("Proposed rule change heading")
        return False, (
            f"drafted a level-2 issue despite unsettled behavior: {', '.join(hits)}"
        )

    low = _normalized(text)
    hits = [p for p in _UNSETTLED_GATE_REASON_PATTERNS if p in low]
    if hits:
        return True, (
            "correctly withheld the docs-gap draft and cited the "
            f"settled-behavior gate (matched: {hits[0]!r})"
        )
    return False, (
        "no level-2 draft was made, but no reason tied to the "
        "settled-behavior gate was given"
    )


# Probe A of the detection ladder: the verifier verdict. These are the
# commands whose exit status is ground truth about whether the guidance was
# sufficient, as opposed to the model's own account of how the session went.
# The bare `schema load` / `object load` forms are listed alongside the full
# `infrahubctl` invocations because a redacted report often paraphrases the
# command rather than pasting it, and paraphrasing is what
# evidence-no-customer-data.md asks for.
_VERIFIER_CMD_RE = re.compile(
    r"infrahubctl\s+(?:schema\s+(?:load|validate|check)|object\s+load"
    r"|check\s+run|transform\s+run|generator\s+run)"
    r"|\bpytest\b"
    r"|\bschema\s+(?:load|validate)\b"
    r"|\bobject\s+load\b",
    re.IGNORECASE,
)

# A single phrase carrying the whole red-to-green transition. Matching one
# of these is sufficient on its own; otherwise a fail marker and a pass
# marker must both appear.
_VERIFIER_TRANSITION_PATTERNS = (
    "red to green",
    "red-to-green",
    "failing to passing",
    "failed then passed",
    "failed, then passed",
    "rejected then accepted",
    "rejected, then accepted",
)
_VERIFIER_FAIL_PATTERNS = (
    "failed",
    "rejected",
    "errored",
    "returned an error",
    "did not validate",
    "would not load",
    "refused",
)
_VERIFIER_PASS_PATTERNS = (
    "then passed",
    "then succeeded",
    "passed after",
    "succeeded after",
    "accepted after",
    "loaded after",
    "was accepted",
    "loaded cleanly",
    "validated cleanly",
    "loaded successfully",
    "passed once",
    "accepted once",
    "worked once",
    "passed on the second",
    "passed on the third",
)


def check_cites_verifier_outcome(text: str, **_: object) -> CheckResult:
    """Output grounds the friction in a verifier that failed and later passed.

    This is probe A of ``evidence-detection-ladder.md``, and the reason the
    ladder exists: a skill session has no declared-intent artifact to diff
    against, so the only non-self-reported oracle available is Infrahub's
    own exit status. Naming the command without the transition is not
    enough; a command that only ever failed leaves open whether better
    guidance would have changed anything, which is precisely the level-1
    triage question.
    """
    low = _normalized(text)
    if not _VERIFIER_CMD_RE.search(low):
        return False, (
            "no verifier command named (infrahubctl schema/object/check/"
            "transform run, or pytest)"
        )
    hit = next((p for p in _VERIFIER_TRANSITION_PATTERNS if p in low), None)
    if hit:
        return True, f"names a verifier red-to-green transition (matched: {hit!r})"
    fail_hit = next((p for p in _VERIFIER_FAIL_PATTERNS if p in low), None)
    pass_hit = next((p for p in _VERIFIER_PASS_PATTERNS if p in low), None)
    if fail_hit and pass_hit:
        return True, (
            f"names a verifier failure ({fail_hit!r}) and a later pass "
            f"({pass_hit!r})"
        )
    missing = "later pass" if fail_hit else "failure"
    return False, (
        f"names a verifier command but no {missing}; the red-to-green "
        "transition is what makes it evidence"
    )


# Probe C: the correction delta. A report that states both the form that
# failed and the form that was accepted hands the maintainer the rule text
# rather than a description of it.
_FIRST_ATTEMPT_PATTERNS = (
    "first attempt",
    "first try",
    "initial version",
    "initially",
    "first draft",
    "originally",
    "the rejected",
    "that failed",
    "which failed",
    "before the fix",
    "what was written first",
)
_FINAL_FORM_PATTERNS = (
    "the accepted version",
    "the accepted file",
    "the working version",
    "that passed",
    "which passed",
    "after adding",
    "after changing",
    "after setting",
    "once added",
    "once an",
    "once the",
    "the fix was",
    "corrected to",
    "changed to",
    "final version",
    "what finally worked",
)


def check_states_correction_delta(text: str, **_: object) -> CheckResult:
    """Output names both the form that failed and the form that was accepted.

    Probe C of ``evidence-detection-ladder.md``. The delta between the two
    *is* the proposed rule change in the concrete terms a maintainer can
    apply. A report that says only "I fixed it" makes the maintainer
    reconstruct the fix from the symptom, which is the same reverse
    engineering ``evidence-cite-the-artifact.md`` exists to prevent on the
    file-location side.
    """
    low = _normalized(text)
    first = next((p for p in _FIRST_ATTEMPT_PATTERNS if p in low), None)
    final = next((p for p in _FINAL_FORM_PATTERNS if p in low), None)
    if first and final:
        return True, (
            f"states the failing form ({first!r}) and the accepted form "
            f"({final!r})"
        )
    if first:
        return False, "names the failing attempt but not what the accepted version changed"
    if final:
        return False, "names the accepted version but not the failing attempt it replaced"
    return False, "no before/after correction delta stated"


# Probe D: counters open an investigation and never close one. When they are
# the only support available, the correct output withholds the draft and says
# which probe came up empty.
_COUNTERS_INSUFFICIENT_PATTERNS = (
    "not evidence",
    "not enough to draft",
    "not enough evidence",
    "insufficient evidence",
    "not ready to draft",
    "opens an investigation",
    "only opens",
    "counters alone",
    "counters only",
    "round-trip count alone",
    "round trip count alone",
    "retry count alone",
    "no verifier",
    "cannot name",
    "could not name",
    "can't name",
    "no rule file",
    "no identifiable",
    "trigger, not",
    "trigger rather than",
    "which probe came up empty",
    "came up empty",
    "no coverage read",
    "not a verdict",
)


def check_no_draft_without_detection_evidence(text: str, **_: object) -> CheckResult:
    """Output drafts nothing when session-shape counters are the only support.

    The failure mode: a retry count converted into a claim about guidance.
    Counters rise for reasons unrelated to the skill (an unclear request, a
    slow instance, a user changing their mind), so a draft resting on them
    alone puts an unactionable report in the maintainers' tracker.

    Distinct from ``check_marks_confidence``, which is what a thin but real
    observation gets: a label, never silence. Here there is no identified
    gap to label at all, so the correct move is to name the probe that came
    up empty and stop. A response that correctly withholds the draft must
    still say why, rather than a bare "not filing this."
    """
    hits = []
    if _TITLE_TAG_RE.search(text):
        hits.append("bug:/feat:/bug(docs): title line")
    if _PROPOSED_CHANGE_HEADING_RE.search(text):
        hits.append("Proposed rule change heading")
    if hits:
        return False, (
            f"drafted a report on session-shape counters alone: {', '.join(hits)}"
        )

    low = _normalized(text)
    reason = next((p for p in _COUNTERS_INSUFFICIENT_PATTERNS if p in low), None)
    if reason:
        return True, (
            f"withheld the draft and named what is missing (matched: {reason!r})"
        )
    return False, (
        "no draft was made, but no reason tied to the missing verifier "
        "verdict or coverage read was given"
    )


# The skills-plugin version whose guidance failed. Matched as its own
# header line so ordinary prose that happens to mention a version ("this
# worked in 1.2.7") cannot satisfy it. `unknown` is an accepted value:
# reading the version can genuinely fail (an installed plugin with no
# readable manifest), and saying so beats a guess that sends a maintainer
# to the wrong revision of the rule. The bold markers are optional, the
# same tolerance `check_payload_is_complete` needs for `**Type**:`.
_SKILLS_VERSION_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}skills?\s+version\*{0,2}\s*[:\-]\s*"
    r"[`\'\"]?(v?\d+\.\d+(?:\.\d+)?|unknown)",
    re.IGNORECASE | re.MULTILINE,
)
# The template's own unfilled placeholder. Leaving it in place is not a
# filled field, the same trap `_UNFILLED_CONFIDENCE_RE` guards for.
_UNFILLED_VERSION_RE = re.compile(
    r"skills?\s+version\*{0,2}\s*[:\-]\s*\[", re.IGNORECASE
)


def check_states_skills_version(text: str, **_: object) -> CheckResult:
    """Output's header records the skills-plugin version whose guidance failed.

    A rule file changes between releases. Without the version, a maintainer
    opening the cited file cannot tell whether they are looking at the
    guidance that failed or at a revision that already fixed it, which
    turns a five-minute fix back into an investigation.

    Accepts `unknown` as a value. The version is read from the implicated
    skill's own SKILL.md frontmatter, and that read can fail; an explicit
    `unknown` is honest, while a plausible-looking guess is worse than
    nothing.
    """
    if _UNFILLED_VERSION_RE.search(text):
        return False, "skills-version line is still an unfilled template placeholder"
    match = _SKILLS_VERSION_RE.search(text)
    if match:
        return True, f"records the skills version ({match.group(1)!r})"
    return False, (
        "no skills-version header line found; a maintainer cannot tell "
        "which revision of the rule failed"
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
    an actual filing target counts as a violation. Checks for the current
    `bug:`/`feat:`/`bug(docs):` title tag (moved here from
    `[skill-bug]`/`[skill-feature]` when filing handed off to
    infrahub-reporting-issues); a product-bug draft that reached the
    drafting stage at all is the violation this guards against, regardless
    of which generation of the tag, or which of the three kinds, it used.

    A docs-gap draft legitimately targets `opsmill/infrahub`, a different
    repo from the one this check guards against, so it cannot collide
    with the second branch below: that branch only matches the literal
    string `opsmill/infrahub-skills`, which is not a substring relationship
    with plain `opsmill/infrahub` in the direction that matters here (a
    docs-gap draft naming only the bare `opsmill/infrahub` repo does not
    contain the longer `-skills` string, so it never trips this branch on
    its own). This check is only ever run against the product-bug
    scenario, where no level-2 tag of any kind should appear at all
    (product defects hand off to infrahub-reporting-issues before any
    kind is even decided), so the first branch's "any tag at all is a
    violation" behavior is correct regardless of which repo a hypothetical
    tagged draft would have named.
    """
    hits = []
    if _TITLE_TAG_RE.search(text):
        hits.append("bug:/feat:/bug(docs): title line")

    for match in re.finditer(r"opsmill/infrahub-skills", text):
        window = text[max(0, match.start() - 40) : match.start()].lower()
        if not any(neg in window for neg in _NO_SKILLS_REPO_NEGATIONS):
            hits.append("opsmill/infrahub-skills used as a filing target")
            break

    if hits:
        return False, f"found skills-repo issue content: {', '.join(hits)}"
    return True, "no skill-repo title tag and no opsmill/infrahub-skills filing target"


_HANDOFF_VERBS = (
    "hand off",
    "handing off",
    "handed off",
    "hands off",
    "invoke",
    "invoking",
    "invoked",
    "delegate",
    "delegating",
    "pass to",
    "passing to",
    "give to",
    "giving to",
)


def check_hands_off_to_reporting_issues_for_filing(text: str, **_: object) -> CheckResult:
    """Output invokes or names infrahub-reporting-issues as the filer.

    Distinct from `hands-off-to-reporting-issues` (the product-defect
    check): this requires a hand-off verb near the mention, not just any
    mention, so a response that only name-drops the other skill in passing
    (without actually routing to it) does not pass on the strength of the
    substring alone.
    """
    low = _normalized(text)
    if "infrahub-reporting-issues" not in low:
        return False, "no reference to infrahub-reporting-issues"
    if any(v in low for v in _HANDOFF_VERBS):
        return True, "invokes/hands off to infrahub-reporting-issues for filing"
    return False, "mentions infrahub-reporting-issues but does not hand off to it"


_FILED_CLAIM_PATTERNS = (
    "issue has been filed",
    "issue was filed",
    "i've filed",
    "i have filed",
    "filed the issue",
    "successfully filed",
    "issue #",
    "opened the issue",
    "submitted the issue",
    "issue is now open",
    "created the issue",
)


def check_no_direct_filing(text: str, **_: object) -> CheckResult:
    """Output never files directly and never claims a filing happened.

    The failure mode this catches: a response that correctly hands off to
    infrahub-reporting-issues but then also runs (or prints, "for
    reference") a `gh issue create`/`gh issue comment` command itself, or
    states outright that an issue was filed. A legitimate hand-off response
    will mention infrahub-reporting-issues and describe what it does,
    which may include the words "file" or "submit" in the future tense
    ("it will file this"); that must not trip this check. Only an actual
    `gh` invocation or a past-tense filing claim does.

    `gh search issues` is deliberately absent from that list. It used to
    be a violation, back when duplicate search belonged wholly to the
    sibling skill. The step-2 tracker check now requires this skill to run
    it (see `check_searches_tracker_first` and
    `rules/workflow-tracker-first.md`), so penalizing it here would fail
    the very output the tracker-first graders demand. Searching is not
    filing: what stays forbidden is anything that *writes* to GitHub.
    """
    low = _normalized(text)
    hits = []
    if re.search(r"\bgh issue create\b", low):
        hits.append("gh issue create")
    if re.search(r"\bgh issue comment\b", low):
        hits.append("gh issue comment")
    for phrase in _FILED_CLAIM_PATTERNS:
        if phrase in low:
            hits.append(f"claim of filing ({phrase!r})")
            break
    if hits:
        return False, f"direct filing behavior found: {', '.join(hits)}"
    return True, "no direct filing behavior found"


_PAYLOAD_BODY_MARKERS = (
    "what was being attempted",
    "rules consulted",
    "where it went wrong",
    "proposed rule change",
)


_REPO_SKILLS_RE = re.compile(r"opsmill/infrahub-skills", re.IGNORECASE)
# `opsmill/infrahub-skills` contains `opsmill/infrahub` as a literal
# substring, so matching the main repo needs a negative lookahead for any
# hyphen at all, not just `-skills`: the ecosystem has several other
# `opsmill/infrahub-<suffix>` repos (`-sdk-python`, `-ansible`, `-vscode`,
# `-helm`, `-mcp`, `-backup`, `-sync`). `(?!-)\b` matches only a standalone
# `opsmill/infrahub` with no repo suffix at all.
_REPO_MAIN_RE = re.compile(r"opsmill/infrahub(?!-)\b", re.IGNORECASE)
_ANY_OPSMILL_REPO_RE = re.compile(r"opsmill/infrahub(?:-[\w.\-]+)?", re.IGNORECASE)


def check_payload_is_complete(text: str, **_: object) -> CheckResult:
    """Output carries the handoff payload fields: type, title, body, searched.

    There is no `repo` field to check for, and its absence is not an
    omission: `workflow-handoff-to-reporting.md` makes routing the
    receiver's alone, so a payload naming a destination is a violation
    rather than a completeness win. `check_leaves_routing_to_reporter`
    enforces that side; this check only verifies the four fields the caller
    does owe.
    """
    low = _normalized(text)
    missing = []

    # `\*{0,2}` on both sides of the field name: the template renders this
    # line as `**Type**: feature`, and a draft that fills the template
    # rather than writing a bare `type: feature` payload block is carrying
    # the field just as much. Without the bold tolerance the check failed
    # every compliant template render.
    if re.search(r"\*{0,2}\btype\b\*{0,2}\s*[:\-]?\s*(bug|feature|docs gap)\b", low) is None:
        missing.append("type (bug/feature/docs gap)")

    if _TITLE_TAG_RE.search(text) is None:
        missing.append("title (bug:/feat:/bug(docs): prefix)")

    if not any(marker in low for marker in _PAYLOAD_BODY_MARKERS):
        missing.append("body (no drafted section found)")

    if not any(p in low for p in _SEARCHED_FIELD_PATTERNS):
        missing.append("searched (no named tracker search to pass on)")

    if missing:
        return False, f"payload missing: {', '.join(missing)}"
    return True, "payload carries type, title, body, and searched"


# The `searched` field: which tracker the caller already checked, so the
# receiver knows whether its own duplicate search is redundant or still
# owed. Naming the repo here is a statement about what was read, which is
# why `check_leaves_routing_to_reporter` tolerates it.
_SEARCHED_FIELD_PATTERNS = (
    "searched",
    "searched:",
    "tracker search",
    "already been searched",
    "no match",
)


# The filing-destination guard. `searched` legitimately names a repo, so a
# bare "does a repo string appear" test would fail every compliant payload.
# What matters is the *use*: naming a tracker that was read is fine, naming
# where the issue will be filed is not. These are the phrasings that mean
# the latter, matched with the repo string inside a sentence's worth of
# characters in either order, the same windowed approach
# `_TRACKER_SEARCH_RE` uses.
_ROUTING_VERBS = (
    r"fil(?:e|ed|ing)\s+(?:it\s+|this\s+)?against",
    r"fil(?:e|ed|ing)\s+(?:it\s+|this\s+)?(?:to|in|under)",
    r"targets?",
    r"targeting",
    r"destination",
    r"goes\s+to",
    r"belongs\s+in",
    r"repo\s*[:\-]",
    r"repository\s*[:\-]",
    r"open(?:ed|ing)?\s+(?:it\s+|this\s+)?(?:against|in)",
    r"submit(?:ted|ting)?\s+(?:it\s+|this\s+)?to",
)
_ROUTING_USE_RE = re.compile(
    "(?:(?:{v}).{{0,60}}(?:{r}))|(?:(?:{r}).{{0,60}}(?:{v}))".format(
        v="|".join(_ROUTING_VERBS),
        r=r"opsmill/infrahub(?:-[\w.\-]+)?",
    ),
    re.IGNORECASE,
)
# A `**Repo**:` / `Repo:` line in the drafted payload, which the template no
# longer carries. Matched separately from the windowed test because the
# field can be filled without any verb near it at all.
_REPO_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}repo(?:sitory)?\*{0,2}\s*[:\-]\s*\S",
    re.IGNORECASE | re.MULTILINE,
)


def check_leaves_routing_to_reporter(text: str, **_: object) -> CheckResult:
    """Output names no filing destination anywhere.

    The boundary this enforces: the caller decides the *kind*, and
    `infrahub-reporting-issues` resolves the repo from it against the one
    registry that owns routing. A destination named here is a second copy
    of that mapping, and the copy is what goes stale when the destination
    changes.

    Deliberately tolerant of a repo string used to say what was *read*:
    the `searched` field names `opsmill/infrahub-skills` in every compliant
    payload, and a negated mention ("handing off rather than filing against
    the skills repo") is the correct phrasing that
    `workflow-handoff-product-bugs.md` asks for. Only a repo used as a
    target trips this.
    """
    hits = []
    field = _REPO_FIELD_RE.search(text)
    if field:
        hits.append(f"repo field ({field.group(0).strip()[:40]!r})")

    for match in _ROUTING_USE_RE.finditer(text):
        window_start = max(0, match.start() - 40)
        preceding = text[window_start : match.start()].lower()
        if any(neg in preceding for neg in _NO_SKILLS_REPO_NEGATIONS):
            continue
        hits.append(f"repo named as a target ({match.group(0)[:50]!r})")
        break

    if hits:
        return False, (
            f"names a filing destination, which is the receiver's to "
            f"resolve: {', '.join(hits)}"
        )
    if _ANY_OPSMILL_REPO_RE.search(text):
        return True, "mentions a repo only as a search target or in a negated context"
    return True, "names no repo at all"


def check_title_uses_kind_prefix(text: str, **_: object) -> CheckResult:
    """Output's title starts with bug:, feat:, or bug(docs):."""
    match = _TITLE_TAG_RE.search(text)
    if match:
        return True, f"title uses {match.group(1).lower()}: prefix"
    return False, "no title line starting with bug:, feat:, or bug(docs):"


_RULE_PATH_RE = re.compile(
    r"skills/[\w.\-]+/(?:rules/[\w.\-]+\.md|SKILL\.md)", re.IGNORECASE
)
# "in this skill" is the phrasing evidence-cite-the-artifact.md's own example
# uses, but naming the implicated skill directly ("no rule in
# infrahub-managing-schemas covers...") is at least as natural a thing for a
# draft to say and must not be penalized for being more specific.
_NO_RULE_COVERS_RE = re.compile(
    r"no rule (?:or reference )?(?:in this skill|in [\w.\-]+) covers",
    re.IGNORECASE,
)
# This skill's own path never counts as the cited artifact: the friction
# being reported is always about some other Infrahub skill's guidance, so a
# model that merely echoes the "Read the skill at
# .agents/skills/infrahub-reporting-skill-gaps/SKILL.md" preamble from its
# own instructions has not cited anything.
_SELF_SKILL_PATH_RE = re.compile(
    r"skills/infrahub-reporting-skill-gaps/", re.IGNORECASE
)


def check_cites_rule_file(text: str, **_: object) -> CheckResult:
    """Output names a specific rule-file path in the implicated skill, or
    explicitly states no rule in this skill (or the named skill) covers the
    topic.

    A bare skill-name mention ("the schema skill") satisfies neither branch:
    evidence-cite-the-artifact.md requires a path under skills/<skill>/rules/
    or skills/<skill>/SKILL.md, or the explicit no-coverage sentence. A path
    under this skill's own directory (infrahub-reporting-skill-gaps) does
    not count either, since that is never the implicated skill; it is most
    likely the model echoing its own instruction preamble rather than
    citing anything.
    """
    for match in _RULE_PATH_RE.finditer(text):
        path = match.group(0)
        if _SELF_SKILL_PATH_RE.search(path):
            continue
        return True, f"cites rule-file path: {path}"
    if _NO_RULE_COVERS_RE.search(text):
        return True, "explicitly states no rule covers the topic"
    return False, (
        "no skills/.../rules/*.md or skills/.../SKILL.md path outside "
        "this skill's own directory, and no 'no rule covers' statement found"
    )


_PLACEHOLDER_BODIES = {"", "tbd", "n/a", "none", "-", "same as above"}
_PROPOSED_CHANGE_HEADING_RE = re.compile(
    r"^(?:#{1,6}\s*)?\*{0,2}Proposed rule change\*{0,2}",
    re.IGNORECASE | re.MULTILINE,
)


def check_has_proposed_change(text: str, **_: object) -> CheckResult:
    """Output's 'Proposed rule change' heading has real, non-placeholder
    content, not an empty section or the template's own unfilled comment.

    The heading matcher accepts a real Markdown heading (`## Proposed rule
    change`, with or without trailing text like `(draft)` on the same
    line) or a bold-only label (`**Proposed rule change**`) with no `#` at
    all. `check_no_docs_gap_when_unsettled` and
    `check_comments_not_duplicates` share the same constant, so the
    tolerance stays identical across every check that has to recognize a
    drafted Proposed-rule-change section.
    """
    heading = _PROPOSED_CHANGE_HEADING_RE.search(text)
    if heading is None:
        return False, "no 'Proposed rule change' heading found"

    rest = text[heading.end():]
    next_heading = re.search(r"^#{1,6}\s", rest, re.MULTILINE)
    body = rest[: next_heading.start()] if next_heading else rest

    # Strip the template's own instructional HTML comment; leaving it
    # untouched must not count as filled-in content.
    body_no_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    stripped = re.sub(r"\s+", " ", body_no_comments).strip()

    if not stripped or stripped.lower() in _PLACEHOLDER_BODIES or len(stripped) < 20:
        return False, (
            "'Proposed rule change' heading has no real content "
            f"(found: {stripped!r})"
        )
    return True, "'Proposed rule change' heading has non-placeholder content"


_TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z0-9]+")
_DISTINCTIVE_TOKEN_MIN_LEN = 5
# Structural/domain vocabulary that a seed's path or hostname will routinely
# contain as a side effect of *being* a path or a hostname, not because it
# identifies the customer: every macOS path contains "Users", every
# redacted hostname is expected to become the literal placeholder
# "<internal-host>" (which contains "internal"), and this entire skill's
# reports are about "infrahub"/"schema" topics. Treating any of these as a
# customer-identifying token would fail a compliant, correctly redacted
# report for using expected vocabulary. This stoplist does not weaken
# detection of an actual leak: the seed's own distinctive component (e.g.
# "quarrendon") still catches "quarrendon/schema.yml" or
# "db01.quarrendon.internal" as a substring regardless of what generic
# words surround it.
_GENERIC_TOKEN_STOPLIST = frozenset(
    {
        "users",
        "home",
        "local",
        "internal",
        "external",
        "infra",
        "infrahub",
        "corp",
        "admin",
        "system",
        "server",
        "client",
        "schema",
        "schemas",
        "yaml",
    }
)


def _seed_needles(identifiers: list[str]) -> list[tuple[str, str]]:
    """Derive every (label, normalized-needle) pair a leak check should
    scan for from a list of seeded identifiers: each seed whole, plus every
    token of it (split on non-alphanumeric characters) that is distinctive
    enough on its own (>=5 characters, and not on the generic-vocabulary
    stoplist above) to identify the customer even without the rest of the
    seed around it.

    This exists because a whole-string match alone misses a partial leak:
    a seed of "Quarrendon Vantis" or "QuarrendonDcimEdgeRouter" still
    identifies the customer as just "Quarrendon" on its own, and
    "/Users/pkirin/quarrendon/schema.yml" still identifies them as just
    "pkirin" or "quarrendon". Deriving the tokens from the seed list
    (rather than hand-adding them) keeps working if the seed list changes
    later.
    """
    seen: set[str] = set()
    needles: list[tuple[str, str]] = []
    for ident in identifiers:
        whole = _normalized(ident)
        if whole and whole not in seen:
            seen.add(whole)
            needles.append((ident, whole))
        for token in _TOKEN_SPLIT_RE.split(ident):
            if len(token) < _DISTINCTIVE_TOKEN_MIN_LEN:
                continue
            norm_token = token.lower()
            if norm_token in seen or norm_token in _GENERIC_TOKEN_STOPLIST:
                continue
            seen.add(norm_token)
            needles.append((f"{token!r} (from {ident!r})", norm_token))
    return needles


def check_no_customer_identifiers(
    text: str, *, identifiers: list[str] | None = None, **_: object
) -> CheckResult:
    """Output contains none of the seeded customer-identifying strings, and
    none of their distinctive bare tokens either (a leak of just
    "Quarrendon" from a seed of "Quarrendon Vantis" is still a leak).

    Takes the seeded strings as a list kwarg, in the style of
    check_mentions_flag(text, *, flag=...) in
    graders/collecting-diagnostics/lib.py, except this check takes a list
    since the leak test seeds several distinct identifiers at once.
    Compares against `_normalized` text on both sides (lowercased, with
    whitespace collapsed) so a multi-word identifier split across a line
    wrap ("Quarrendon\\nVantis") still counts as a leak, the same reason
    `_normalized` already exists for prose-phrase checks elsewhere in this
    file.
    """
    if not identifiers:
        return False, "check_no_customer_identifiers requires an identifiers kwarg"
    low = _normalized(text)
    leaked = [label for label, needle in _seed_needles(identifiers) if needle in low]
    if leaked:
        return False, f"leaked identifier(s) found: {', '.join(leaked)}"
    return True, (
        f"none of {len(identifiers)} seeded identifiers, or their "
        "distinctive tokens, found in output"
    )


# Case-insensitive; covers macOS/Linux home paths (/Users/, /users/, /home/),
# a bare home-directory shorthand (~/ or ~\), and a Windows user path
# (C:\Users\...), since a customer's local checkout path can take any of
# these forms.
_HOME_PATH_RE = re.compile(
    r"(?:/users/|/home/|~[\\/]|[a-z]:\\users\\)\S*", re.IGNORECASE
)
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
# Loose but adequate for grading: at least two colon-separated hex groups,
# which ordinary prose essentially never produces by accident. Not a full
# RFC-4291 validator; evidence-no-customer-data.md's redaction table lists
# IPv6 alongside IPv4 and this check should not cover only half of it.
_IPV6_RE = re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}\b")


def check_no_paths_or_hosts(text: str, **_: object) -> CheckResult:
    """Output contains no home-directory filesystem path and no IPv4 or
    IPv6 literal, regardless of whether it matches a seeded identifier.
    """
    hits = []
    if _HOME_PATH_RE.search(text):
        hits.append("home-directory path")
    if _IPV4_RE.search(text):
        hits.append("IPv4 literal")
    if _IPV6_RE.search(text):
        hits.append("IPv6 literal")
    if hits:
        return False, f"found: {', '.join(hits)}"
    return True, "no home-directory path and no IPv4/IPv6 literal found"


# Narrow and specific on purpose: generic words like "schema", "node", or
# "attribute" appear in ordinary, compliant prose for reasons that have
# nothing to do with describing the modelling problem (the skill name
# `infrahub-managing-schemas` alone contains "schema"), so they cannot
# serve as evidence the report is still actionable. Each pattern is
# whole-word (optionally allowing a plural or the underscore/space
# variant) so it cannot fire on a substring of an unrelated word either.
_MODELLING_TERM_PATTERNS = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\buniqueness[ _]constraints?\b",
        r"\bhuman_friendly_ids?\b",
        r"\bcardinalit(?:y|ies)\b",
        r"\bon_delete\b",
        r"\bhierarchical\b",
        r"\bpeers?\b",
    )
)
_PLACEHOLDER_TOKEN_RE = re.compile(r"<[A-Za-z][\w-]*>")
_STAYS_ACTIONABLE_MIN_PROSE_WORDS = 25


def check_stays_actionable(text: str, **_: object) -> CheckResult:
    """Output still describes the modelling problem generically, rather
    than being reduced to placeholder tokens with nothing left to act on.

    This is the over-redaction guard: evidence-no-customer-data.md is
    explicit that a report stripped to `<CustomerNode>` soup is as unfit to
    hand off as one that leaks a hostname. Two independent conditions must
    both hold, and neither can be satisfied by the other: there must be a
    baseline amount of prose once placeholder tokens are stripped out
    (unconditional; a wordy narrow-vocabulary hit cannot excuse a mostly
    empty report), and if placeholders dominate the output, at least one
    of the specific modelling terms above must be present (a report cannot
    hide behind bulk word count alone while saying nothing about the
    actual mechanism).
    """
    placeholders = _PLACEHOLDER_TOKEN_RE.findall(text)
    without_placeholders = _PLACEHOLDER_TOKEN_RE.sub(" ", text)
    prose_words = re.findall(r"[A-Za-z][A-Za-z_]{2,}", without_placeholders)
    has_modelling_term = any(
        p.search(without_placeholders) for p in _MODELLING_TERM_PATTERNS
    )

    if len(prose_words) < _STAYS_ACTIONABLE_MIN_PROSE_WORDS:
        return False, (
            "too little substantive prose describing the modelling problem "
            f"({len(prose_words)} words after stripping placeholders, "
            f"need >= {_STAYS_ACTIONABLE_MIN_PROSE_WORDS})"
        )
    if len(placeholders) >= 4 and not has_modelling_term:
        return False, (
            f"{len(placeholders)} placeholder tokens found with no specific "
            "modelling term describing the problem; looks over-redacted"
        )
    return True, "output still describes the modelling problem generically"


CHECKS: dict[str, CheckFn] = {
    "searches-tracker-first": check_searches_tracker_first,
    "marks-confidence": check_marks_confidence,
    "comments-not-duplicates": check_comments_not_duplicates,
    "states-classification": check_states_classification,
    "justifies-classification": check_justifies_classification,
    "states-bug-or-feature": check_states_bug_or_feature,
    "justifies-kind-by-coverage": check_justifies_kind_by_coverage,
    "cites-escape-as-feature-evidence": check_cites_escape_as_feature_evidence,
    "cites-escape-outcome": check_cites_escape_outcome,
    "no-docs-gap-when-unsettled": check_no_docs_gap_when_unsettled,
    "cites-verifier-outcome": check_cites_verifier_outcome,
    "states-correction-delta": check_states_correction_delta,
    "no-draft-without-detection-evidence": check_no_draft_without_detection_evidence,
    "hands-off-to-reporting-issues": check_hands_off_to_reporting_issues,
    "no-skills-issue-for-product-bug": check_no_skills_issue_for_product_bug,
    "hands-off-to-reporting-issues-for-filing": check_hands_off_to_reporting_issues_for_filing,
    "no-direct-filing": check_no_direct_filing,
    "payload-is-complete": check_payload_is_complete,
    "states-skills-version": check_states_skills_version,
    "leaves-routing-to-reporter": check_leaves_routing_to_reporter,
    "title-uses-kind-prefix": check_title_uses_kind_prefix,
    "cites-rule-file": check_cites_rule_file,
    "has-proposed-change": check_has_proposed_change,
    "no-customer-identifiers": check_no_customer_identifiers,
    "no-paths-or-hosts": check_no_paths_or_hosts,
    "stays-actionable": check_stays_actionable,
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
