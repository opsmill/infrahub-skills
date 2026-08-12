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


# Level-2 title tag. It has moved twice: `[skill-friction]` first, then
# `[skill-bug]`/`[skill-feature]` once level-2 kind splitting shipped, and
# now a bare `bug:`/`feat:` line prefix once filing moved to
# infrahub-reporting-issues. Anchored to the start of a markdown line
# (optionally after heading hashes or a bold-open marker) so ordinary prose
# like "there's a bug: the counter increments twice" does not false-match;
# a real title occupies its own line.
_TITLE_TAG_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(bug|feat):\s*\S", re.IGNORECASE | re.MULTILINE
)


def check_no_draft_on_single_session(text: str, **_: object) -> CheckResult:
    """Output does not draft a full issue from a single, uncorroborated session."""
    has_issue_title = _TITLE_TAG_RE.search(text) is not None
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
            hits.append("bug:/feat: title line")
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
    passes an unresolvable case is worse than one that says so. The title
    tag itself is stripped before this scan (using a real-newline-preserving
    lowercase, not `_normalized`, so the line-anchored strip actually lines
    up) so a `bug:` title's own substring "bug" is never counted as a prose
    mention; a `feat:` tag never contains the word "feature" so it needs no
    stripping, but the substitution covers both for symmetry.
    """
    low = text.lower()
    tag_match = _TITLE_TAG_RE.search(text)
    has_bug_tag = bool(tag_match and tag_match.group(1).lower() == "bug")
    has_feature_tag = bool(tag_match and tag_match.group(1).lower() == "feat")

    prose = re.sub(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:bug|feat):\s*", " ", low, flags=re.MULTILINE)
    named_bug = re.search(r"\bbug\b", prose) is not None
    named_feature = re.search(r"\bfeature\b", prose) is not None

    if not (named_bug or named_feature):
        return False, "no explicit bug/feature classification named"
    if not (has_bug_tag or has_feature_tag):
        return False, "kind named but no bug:/feat: title prefix found"

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
            return False, "stated kind is bug but title prefix uses feat:"
        return True, "names bug and uses matching bug: title prefix"
    if not has_feature_tag:
        return False, "stated kind is feature but title prefix uses bug:"
    return True, "names feature and uses matching feat: title prefix"


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
    an actual filing target counts as a violation. Checks for the current
    `bug:`/`feat:` title tag (moved here from `[skill-bug]`/`[skill-feature]`
    when filing handed off to infrahub-reporting-issues); a product-bug
    draft that reached the drafting stage at all is the violation this
    guards against, regardless of which generation of the tag it used.
    """
    hits = []
    if _TITLE_TAG_RE.search(text):
        hits.append("bug:/feat: title line")

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
    reference") a `gh issue create`/`gh search issues` command itself, or
    states outright that an issue was filed. A legitimate hand-off response
    will mention infrahub-reporting-issues and describe what it does,
    which may include the words "file" or "submit" in the future tense
    ("it will file this"); that must not trip this check. Only an actual
    `gh` invocation or a past-tense filing claim does.
    """
    low = _normalized(text)
    hits = []
    if re.search(r"\bgh issue create\b", low):
        hits.append("gh issue create")
    if re.search(r"\bgh search issues\b", low):
        hits.append("gh search issues")
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


def check_payload_is_complete(text: str, **_: object) -> CheckResult:
    """Output carries all four handoff payload fields: repo, type, title, body."""
    low = _normalized(text)
    missing = []

    if "opsmill/infrahub-skills" not in low:
        missing.append("repo (opsmill/infrahub-skills)")

    if re.search(r"\btype\b\s*[:\-]?\s*(bug|feature)\b", low) is None:
        missing.append("type (bug/feature)")

    if _TITLE_TAG_RE.search(text) is None:
        missing.append("title (bug:/feat: prefix)")

    if not any(marker in low for marker in _PAYLOAD_BODY_MARKERS):
        missing.append("body (no drafted section found)")

    if missing:
        return False, f"payload missing: {', '.join(missing)}"
    return True, "payload carries repo, type, title, and body"


def check_title_uses_kind_prefix(text: str, **_: object) -> CheckResult:
    """Output's title starts with bug: or feat:."""
    match = _TITLE_TAG_RE.search(text)
    if match:
        return True, f"title uses {match.group(1).lower()}: prefix"
    return False, "no title line starting with bug: or feat:"


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
    all, matching the tolerance check_no_draft_on_single_session already
    has for the Proposed-rule-change section at any heading depth.
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
    "hands-off-to-reporting-issues-for-filing": check_hands_off_to_reporting_issues_for_filing,
    "no-direct-filing": check_no_direct_filing,
    "payload-is-complete": check_payload_is_complete,
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
