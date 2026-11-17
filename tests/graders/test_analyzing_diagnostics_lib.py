"""Tests for the report parsers in graders/analyzing-diagnostics/lib.py.

Three parsers decided scores on the release smoke run without ever being
tested, and each failed correct reports:

* ``_incident_sections`` counted `### Incident Correlation` and
  `## Incident Summary` as incidents, so a report that also wrote one of
  those failed evidence, severity, and incident-count checks.
* ``_root_windows`` read the root line plus the next line only, so a root
  written under a `### Root Cause` heading, with a blank line before its
  evidence, was never seen.
* ``_gh_search_commands`` stopped at the first line break, so a query
  wrapped inside backticks (as the skill's own example wraps it) lost its
  keywords, and a token leaked on the second line went unseen.

Each parser gets the four fixtures dev/guidelines/graders.md asks for.
"""

import importlib.util
from pathlib import Path

import pytest

_GRADER_DIR = (
    Path(__file__).resolve().parent.parent.parent / "graders" / "analyzing-diagnostics"
)

# Load lib.py by path under a unique name: the task graders import it as
# `lib`, which would collide with every other grader's lib.py in sys.modules.
_spec = importlib.util.spec_from_file_location(
    "analyzing_diagnostics_graders_lib", _GRADER_DIR / "lib.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

check_root_service = _mod.check_root_service
check_incident_grouping = _mod.check_incident_grouping
check_cites_bundle_evidence = _mod.check_cites_bundle_evidence
check_severity_labels = _mod.check_severity_labels
check_search_keyword = _mod.check_search_keyword
check_search_excludes_token = _mod.check_search_excludes_token


# --- incident sections -------------------------------------------------------

TEMPLATE_REPORT = """# Findings

Deployment: Infrahub 1.2.4 (community). Manifest: 8/8 collectors ok.

## Incident 1: message queue down, server cascades (CRITICAL)

- Root: broker stopped — bundle/message-queue/rabbitmq.log
  > Stopping RabbitMQ
- Cascade: downstream connection errors in bundle/logs/server/server.log
"""

# Same incident, plus a summary section about it: the summary is not an
# incident, so it needs neither a bundle path nor a severity of its own.
WITH_SUMMARY = TEMPLATE_REPORT + """
## Incident Summary

One incident; the server errors are a consequence of the broker stop.
"""

UNCITED = TEMPLATE_REPORT + """
## Incident 2: slow UI

- Root: unclear
"""

# Near-miss: `Incident:` opens an incident, so the uncited one still counts.
UNCITED_COLON = TEMPLATE_REPORT + """
### Incident: slow UI

- Root: unclear
"""


# A dash after "Incident" opens an incident too (review of #226).
DASH_HEADING = TEMPLATE_REPORT.replace(
    "## Incident 1: message queue down, server cascades (CRITICAL)",
    "## Incident - message queue down, server cascades (CRITICAL)",
)


@pytest.mark.parametrize(
    "report", [TEMPLATE_REPORT, WITH_SUMMARY, DASH_HEADING], ids=["template", "with-summary", "dash"]
)
def test_incident_sections_pass(report: str) -> None:
    assert check_cites_bundle_evidence(report)[0]
    assert check_severity_labels(report)[0]
    assert check_incident_grouping(report, max_incidents=1)[0]


# Near-miss: a hyphenated word is not a dash heading, so this section is not
# an incident and needs no bundle path or severity (review of #247).
HYPHENATED_HEADING = TEMPLATE_REPORT + """
## Incident-free services

The database and the cache show no errors.
"""


def test_hyphenated_heading_is_not_an_incident() -> None:
    assert len(_mod._incident_sections(HYPHENATED_HEADING)) == 1
    assert check_cites_bundle_evidence(HYPHENATED_HEADING)[0]
    assert check_severity_labels(HYPHENATED_HEADING)[0]
    assert check_incident_grouping(HYPHENATED_HEADING, max_incidents=1)[0]


@pytest.mark.parametrize("report", [UNCITED, UNCITED_COLON], ids=["numbered", "colon"])
def test_uncited_incident_fails(report: str) -> None:
    assert not check_cites_bundle_evidence(report)[0]
    assert not check_incident_grouping(report, max_incidents=1)[0]


# --- root windows ------------------------------------------------------------

HEADING_ROOT = """## Incident 1: broker outage (CRITICAL)

### Root Cause

The broker stopped first.

Evidence: bundle/message-queue/rabbitmq.log
> Stopping RabbitMQ

### Cascade

Downstream errors in bundle/logs/server/server.log.
"""

BLANK_LINE_ROOT = """## Incident 1: broker outage (CRITICAL)

- Root: broker stopped

  bundle/message-queue/rabbitmq.log
- Cascade: downstream errors in bundle/logs/server/server.log
"""

WRONG_ROOT = TEMPLATE_REPORT.replace(
    "broker stopped — bundle/message-queue/rabbitmq.log",
    "connection refused — bundle/logs/server/server.log",
)

# Near-miss: a Root Cause heading whose evidence is the server log, with the
# broker named only in the next section. The section window must stop there.
HEADING_ROOT_WRONG = """## Incident 1: broker outage (CRITICAL)

### Root Cause

Connection refused.

Evidence: bundle/logs/server/server.log

### Cascade

The message-queue restarts afterwards (bundle/message-queue/rabbitmq.log).
"""


# A heading that mentions the root without starting with it, and the
# evidence path three lines down (review of #247).
LIKELY_ROOT_HEADING = """## Incident 1: broker outage (CRITICAL)

### Likely root cause

The broker stopped first.

Evidence: bundle/message-queue/rabbitmq.log
> Stopping RabbitMQ

### Cascade

Downstream errors in bundle/logs/server/server.log.
"""

# A `Root:` paragraph, not a list item: it owns the next non-blank line.
PARAGRAPH_ROOT = """## Incident 1: broker outage (CRITICAL)

**Root cause:** broker stopped
bundle/message-queue/rabbitmq.log

**Cascade:** downstream errors in bundle/logs/server/server.log
"""


# The evidence on its own sibling item, as report-evidence-per-finding.md
# writes it (review of #247).
EVIDENCE_ITEM = """## Incident 1: broker memory alarm (CRITICAL)

- Root: memory resource limit alarm on rabbit@mq-1 (10:11:52)
- Evidence: bundle/logs/message-queue/message-queue-1.log
- Cascade: downstream connection errors in bundle/logs/server/server.log
- Recommendation: raise the memory limit of the broker
"""

# The same report with indented headings.
INDENTED_HEADINGS = TEMPLATE_REPORT.replace("## Incident 1", "  ## Incident 1")


@pytest.mark.parametrize(
    "report",
    [
        TEMPLATE_REPORT,
        HEADING_ROOT,
        BLANK_LINE_ROOT,
        LIKELY_ROOT_HEADING,
        PARAGRAPH_ROOT,
        EVIDENCE_ITEM,
        INDENTED_HEADINGS,
    ],
    ids=[
        "template",
        "heading",
        "blank-line",
        "likely-root-heading",
        "paragraph",
        "evidence-item",
        "indented-headings",
    ],
)
def test_root_attributed(report: str) -> None:
    assert check_root_service(report, service="message-queue")[0]
    assert check_incident_grouping(report, max_incidents=1)[0]


# Near-miss: the incident heading says "root cause" and the root is the
# server; the broker appears only on the Cascade line. A heading that only
# mentions the root must not make its whole section a root window (review of
# #226).
ROOT_IN_INCIDENT_HEADING = """## Incident 1: server crash is the root cause (CRITICAL)

- Root: server crashed — bundle/logs/server/server.log
  > Worker exited with code 137
- Cascade: message-queue connections dropped (bundle/message-queue/rabbitmq.log)
"""


# Near-miss: a root heading above the template lines. The root is read from
# the `- Root:` line, never from the `- Cascade:` line, whatever the heading
# says (review of #247).
ROOT_HEADING_OVER_LABELS = """## Incident 1: server crash (CRITICAL)

### Root cause analysis

- Root: server crashed
- Cascade: message-queue connections dropped (bundle/message-queue/rabbitmq.log)
"""

# Near-miss: a root heading with no `- Root:` line. The Cascade item under it
# is still not the root.
ROOT_HEADING_CASCADE_ITEM = """## Incident 1: server crash (CRITICAL)

### Root cause analysis

The server crashed first (bundle/logs/server/server.log).

- Cascade: message-queue connections dropped
  (bundle/message-queue/rabbitmq.log)
"""

# Near-miss: the broker is named in prose after the Root item, at the same
# indentation, so it is not part of the item.
PROSE_AFTER_ROOT_ITEM = """## Incident 1: server crash (CRITICAL)

- Root: server crashed — bundle/logs/server/server.log
  > Worker exited with code 137

The message-queue is healthy and logs downstream errors only.
"""


# Near-miss: the broker is named on a labelled sibling item that is not
# evidence, after the Evidence item of the root.
LABELLED_SIBLING = """## Incident 1: server crash (CRITICAL)

- Root: server crashed (10:11:52)
- Evidence: bundle/logs/server/server.log
- Recommendation: check the message-queue credentials of the server
- Cascade: task-workers lost their connection
"""


@pytest.mark.parametrize(
    "report",
    [
        WRONG_ROOT,
        HEADING_ROOT_WRONG,
        ROOT_IN_INCIDENT_HEADING,
        ROOT_HEADING_OVER_LABELS,
        ROOT_HEADING_CASCADE_ITEM,
        PROSE_AFTER_ROOT_ITEM,
        LABELLED_SIBLING,
    ],
    ids=[
        "template",
        "heading",
        "root-in-incident-heading",
        "root-heading-over-labels",
        "root-heading-cascade-item",
        "prose-after-root-item",
        "labelled-sibling",
    ],
)
def test_wrong_root_fails(report: str) -> None:
    assert not check_root_service(report, service="message-queue")[0]


# --- gh search commands ------------------------------------------------------

ONE_LINE = 'Query: `gh search issues --repo opsmill/infrahub "InitializationError message broker"`\n'

# The skill's own example wraps the command inside the backticks.
WRAPPED = 'Queries tried: `gh search issues --repo\n  opsmill/infrahub "InitializationError message broker"`\n'

CONTINUED = '```bash\ngh search issues --repo opsmill/infrahub \\\n  "InitializationError message broker"\n```\n'

LEAKED = 'Query: `gh search issues --repo opsmill/infrahub "InitializationError rabbitmq-7f9c4d.acme.net"`\n'

# Near-miss: the leak sits on the wrapped second line, which a first-line
# reader never sees.
LEAKED_WRAPPED = 'Queries tried: `gh search issues --repo\n  opsmill/infrahub "InitializationError rabbitmq-7f9c4d.acme.net"`\n'


@pytest.mark.parametrize("report", [ONE_LINE, WRAPPED, CONTINUED], ids=["one-line", "wrapped", "continued"])
def test_stable_query_passes(report: str) -> None:
    assert check_search_keyword(report, keyword="InitializationError")[0]
    assert check_search_excludes_token(report, token="acme")[0]


@pytest.mark.parametrize("report", [LEAKED, LEAKED_WRAPPED], ids=["one-line", "wrapped"])
def test_leaked_token_fails(report: str) -> None:
    assert not check_search_excludes_token(report, token="acme")[0]


def test_prose_after_command_is_not_query() -> None:
    """Prose on the next line may name the stripped token."""
    report = ONE_LINE + "Stripped the acme.net hostname from the key.\n"
    assert check_search_excludes_token(report, token="acme")[0]


# --- pasted excerpt: analyze first, manifest not provided --------------------
#
# rules/workflow-ask-bundle-location.md and rules/workflow-manifest-first.md,
# graded by the issue-matching task, whose prompt pastes one log and no
# manifest (review of #226).

ISSUE_MATCHING_CHECKS = [
    "analyzes-pasted-excerpt",
    "manifest-not-provided",
    "cites-bundle-evidence",
    "github-search",
    ("search-keyword", {"keyword": "InitializationError"}),
    ("search-excludes-token", {"token": "acme"}),
    "no-direct-issue-filing",
    "cross-link-reporting-issues",
]

EXCERPT_REPORT = """# Findings

Deployment: Infrahub version unknown. Manifest: not provided (one pasted log).

## Incident 1: task-workers cannot reach the message broker (CRITICAL)

- Root: InitializationError at startup — bundle/logs/task-worker/task-worker-1.log
  > infrahub.exceptions.InitializationError: Unable to connect to the message broker

## Known issues

`gh search issues --repo opsmill/infrahub "InitializationError" "message broker"`

To file or comment on an issue, use infrahub-reporting-issues.

## Open questions

- The manifest and the other services are not in the excerpt. Where is the full bundle?
"""

# Benoit's first case: the report opens by asking for the bundle path.
ASKS_FIRST = (
    "Before I analyze this, where is the full bundle directory?\n\n"
    + EXCERPT_REPORT.replace(
        "\n## Open questions\n\n- The manifest and the other services are not in the excerpt. "
        "Where is the full bundle?\n",
        "",
    )
)

# Benoit's second case: a collector count inferred from one pasted log.
INFERRED_COUNT = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).", "Manifest: 1/1 collectors ok."
)

# Near-miss: says "not provided", then still infers a count.
NOT_PROVIDED_AND_COUNT = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).",
    "Manifest: not provided, so 1 of 1 collectors assumed ok.",
)

# Near-miss: names the manifest but never says it is missing.
MANIFEST_NAMED_ONLY = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).", "Manifest: see bundle_information.json."
)


# A count next to "not provided", with a collector type in the "of" form
# (review of #247).
NOT_PROVIDED_TYPED_OF = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).",
    "Manifest: not provided; 3 of 4 log collectors succeeded.",
)

# A bare count, and "none" on the Manifest line that is not its value
# (review of #247).
BARE_COUNT_NONE_FAILED = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).",
    "Manifest: all 8 collectors succeeded, none failed.",
)

# Near-miss: no count, and "none"/"missing" near "Manifest" without being its
# value.
NONE_NEAR_MANIFEST = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).",
    "Manifest: read, none of the entries are missing.",
)

_NO_OPEN_QUESTION = EXCERPT_REPORT.replace(
    "\n## Open questions\n\n- The manifest and the other services are not in the excerpt. "
    "Where is the full bundle?\n",
    "",
)

# Near-miss: a question for the bundle with no location word (review of #247).
ASKS_TO_PROVIDE = "Before I start, can you provide the full bundle?\n\n" + _NO_OPEN_QUESTION

# Near-miss: a request for the bundle with no question mark (review of #247).
REQUESTS_PATH = "Please send me the path to the full bundle.\n\n" + _NO_OPEN_QUESTION

# Near-miss: a request for the manifest, not the bundle.
REQUESTS_MANIFEST = "I need the bundle_information.json file first.\n\n" + _NO_OPEN_QUESTION

# Compliant: names the bundle before the analysis without asking for it.
STATES_SCOPE = (
    "You pasted one log, so I do not need the full bundle to start.\n\n" + EXCERPT_REPORT
)

# Compliant: other wordings of "not provided".
NOT_PROVIDED_WORDINGS = [
    "**Manifest:** not provided.",
    "**Manifest**: not included in the excerpt.",
    "The manifest was not pasted.",
    "No manifest in the excerpt.",
    "Manifest (bundle_information.json): missing.",
]


@pytest.mark.parametrize("wording", NOT_PROVIDED_WORDINGS)
def test_not_provided_wordings_pass(wording: str) -> None:
    report = EXCERPT_REPORT.replace("Manifest: not provided (one pasted log).", wording)
    assert _mod.check_manifest_not_provided(report)[0]


def test_scope_statement_before_analysis_passes() -> None:
    assert _mod.check_analyzes_pasted_excerpt(STATES_SCOPE)[0]


def test_negated_request_before_analysis_passes() -> None:
    """Near-miss: a polite sentence that asks for nothing."""
    report = "Please do not provide the full bundle yet.\n\n" + EXCERPT_REPORT
    assert _mod.check_analyzes_pasted_excerpt(report)[0]


def _run(tmp_path: Path, report: str) -> dict:
    out = tmp_path / "output.md"
    out.write_text(report)
    return _mod.run_checks(ISSUE_MATCHING_CHECKS, out)


def test_excerpt_report_passes(tmp_path: Path) -> None:
    result = _run(tmp_path, EXCERPT_REPORT)
    assert result["score"] == 1.0, result["details"]


@pytest.mark.parametrize(
    ("report", "check"),
    [
        (ASKS_FIRST, "analyzes-pasted-excerpt"),
        (INFERRED_COUNT, "manifest-not-provided"),
        (NOT_PROVIDED_AND_COUNT, "manifest-not-provided"),
        (MANIFEST_NAMED_ONLY, "manifest-not-provided"),
        (NOT_PROVIDED_TYPED_OF, "manifest-not-provided"),
        (BARE_COUNT_NONE_FAILED, "manifest-not-provided"),
        (NONE_NEAR_MANIFEST, "manifest-not-provided"),
        (ASKS_TO_PROVIDE, "analyzes-pasted-excerpt"),
        (REQUESTS_PATH, "analyzes-pasted-excerpt"),
        (REQUESTS_MANIFEST, "analyzes-pasted-excerpt"),
    ],
    ids=[
        "asks-first",
        "inferred-count",
        "not-provided-and-count",
        "manifest-named-only",
        "not-provided-typed-of",
        "bare-count-none-failed",
        "none-near-manifest",
        "asks-to-provide",
        "requests-path",
        "requests-manifest",
    ],
)
def test_excerpt_rule_violation_fails_on_its_check(tmp_path: Path, report: str, check: str) -> None:
    result = _run(tmp_path, report)
    failed = [c["name"] for c in result["checks"] if not c["passed"]]
    assert failed == [check], result["details"]


# Near-miss: the count with a collector type between ratio and "collectors".
TYPED_COUNT = EXCERPT_REPORT.replace(
    "Manifest: not provided (one pasted log).", "Manifest: 3/4 log collectors succeeded."
)


def test_typed_collector_count_fails() -> None:
    assert not _mod.check_manifest_not_provided(TYPED_COUNT)[0]


def test_question_naming_a_bundle_path_is_a_question() -> None:
    """Near-miss: the first analysis marker sits inside the question."""
    report = "Is the bundle in bundle/ under your home folder?\n\n" + EXCERPT_REPORT
    assert not _mod.check_analyzes_pasted_excerpt(report)[0]


def test_question_only_has_no_analysis() -> None:
    assert not _mod.check_analyzes_pasted_excerpt("Where is the bundle directory?\n")[0]
