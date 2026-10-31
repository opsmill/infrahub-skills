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


@pytest.mark.parametrize("report", [TEMPLATE_REPORT, WITH_SUMMARY], ids=["template", "with-summary"])
def test_incident_sections_pass(report: str) -> None:
    assert check_cites_bundle_evidence(report)[0]
    assert check_severity_labels(report)[0]
    assert check_incident_grouping(report, max_incidents=1)[0]


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


@pytest.mark.parametrize(
    "report", [TEMPLATE_REPORT, HEADING_ROOT, BLANK_LINE_ROOT],
    ids=["template", "heading", "blank-line"],
)
def test_root_attributed(report: str) -> None:
    assert check_root_service(report, service="message-queue")[0]


@pytest.mark.parametrize("report", [WRONG_ROOT, HEADING_ROOT_WRONG], ids=["template", "heading"])
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
