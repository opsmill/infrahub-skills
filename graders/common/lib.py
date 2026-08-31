"""Shared grader library for cross-cutting infrahub-common rules.

Currently covers the documentation-fallback behavior of
`workflow-information-priority.md`: when a task is not covered by any
loaded skill, the answer must consult the official docs and say so.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(["docs-fallback"], Path("output.md"))
    print(result)
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_output(path: Path) -> str:
    """Read the model's output file as text."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


# Any of these phrases signals the answer flags the point as outside the
# skill's tested guidance (a gap) and/or leans on the official docs.
_CAVEAT_MARKERS = [
    "not covered",
    "not part of",
    "outside",
    "isn't covered",
    "is not covered",
    "verify",
    "official doc",
    "docs say",
    "gap",
    "not in the skill",
]


def check_docs_fallback(text: str) -> tuple[bool, str]:
    """A gap-fill answer must cite a docs.infrahub.app page and flag the gap.

    Fails if the answer silently resolves the gap from training with no
    documentation citation, or cites the docs without flagging that the
    point is outside the skill's tested rules.
    """
    lower = text.lower()
    cites = "docs.infrahub.app" in lower
    caveat = any(marker in lower for marker in _CAVEAT_MARKERS)
    if not cites:
        return False, "Answer does not cite a docs.infrahub.app page"
    if not caveat:
        return False, "Answer cites docs but lacks a gap/verify caveat"
    return True, "Cites docs.infrahub.app and flags the gap"


# ---------------------------------------------------------------------------
# infrahubctl command truth
#
# The tree is duplicated from scripts/check-cli-invocations.py rather than
# imported, per dev/guides/adding-a-rule.md: graders stay standalone. That
# script checks what the *skills* print; these checks what the *model*
# prints, which is the outcome the rules exist to change. Read from
# infrahub-sdk 1.23.1.
# ---------------------------------------------------------------------------

_CLI_GROUPS: dict[str, set[str]] = {
    "branch": {"create", "delete", "list", "merge", "rebase", "report", "validate"},
    "graphql": {"export-schema", "generate-return-types", "query-report"},
    "marketplace": {"get", "list", "search", "show"},
    "menu": {"load", "validate"},
    "object": {"create", "delete", "get", "load", "update", "validate"},
    "repository": {"add", "init", "list"},
    "schema": {"check", "export", "format", "list", "load", "show"},
    "task": {"list"},
    "telemetry": {"export", "list"},
    "validate": {"graphql-query", "schema"},
}

_CLI_LEAVES: set[str] = {
    "check", "dump", "generator", "info", "load",
    "protocols", "render", "run", "transform", "version",
}

# A generic verb after a leaf command is an invented subcommand: the leaf
# takes its target as a positional argument.
_CLI_SUSPICIOUS: set[str] = {
    "run", "list", "get", "create", "delete", "load", "dump",
    "check", "validate", "execute", "show", "new", "add", "export", "import",
}

_CLI_INVOCATION = re.compile(r"infrahubctl\s+([a-z][a-z0-9_-]*)(?:\s+([a-z][a-z0-9_-]*))?")


def check_cli_commands_exist(text: str) -> tuple[bool, str]:
    """Every `infrahubctl ...` command in the answer must be a real command.

    Guards the invented-subcommand class directly: `schema validate`,
    `check run`, `generator list`, `import load` all read plausibly and all
    fail on first use.
    """
    bad: list[str] = []
    for first, second in _CLI_INVOCATION.findall(text):
        shown = f"infrahubctl {first}" + (f" {second}" if second else "")
        if first in _CLI_GROUPS:
            if second and second not in _CLI_GROUPS[first]:
                bad.append(shown)
        elif first in _CLI_LEAVES:
            if second in _CLI_SUSPICIOUS:
                bad.append(shown)
        else:
            bad.append(shown)
    if bad:
        return False, f"command(s) that do not exist: {sorted(set(bad))}"
    return True, "all infrahubctl commands referenced exist"


def check_python_transform_dry_run(text: str) -> tuple[bool, str]:
    """A Python transform must be dry-run with `transform`, never `render`.

    `render` resolves names against `jinja2_transforms` only, so pointing it
    at a `python_transforms` entry prints "Unable to find <name>", which
    reads as an unregistered transform rather than the wrong command. The
    reader concludes the gate is unavailable and skips it.
    """
    lower = text.lower()
    if "infrahubctl transform" not in lower:
        return False, "does not recommend `infrahubctl transform` for the Python transform"
    # `render` may legitimately appear to draw the contrast; what must not
    # appear is render aimed at the named python transform.
    misuse = re.search(r"infrahubctl\s+render\s+spine_config", lower)
    if misuse:
        return False, "recommends `infrahubctl render` for a python_transforms entry"
    return True, "uses `infrahubctl transform` for the Python transform"


_WRITE_PROBE_MARKERS = [
    "branch create",
    "throwaway branch",
    "write probe",
    "infrahub_api_token",
]


def check_preflight_write_probe(text: str) -> tuple[bool, str]:
    """A pre-flight before a write must not rest on `infrahubctl info` alone.

    With no token set, `info` skips the user lookup entirely and reports a
    green status, so it passes on exactly the misconfiguration it exists to
    catch. The answer has to check the token or probe a write.
    """
    lower = text.lower()
    if not any(m in lower for m in _WRITE_PROBE_MARKERS):
        return False, (
            "no token check or write probe; expected one of "
            f"{_WRITE_PROBE_MARKERS}"
        )
    claims_token_valid = re.search(
        r"info[^.\n]{0,80}(token is valid|validates the token|confirms the token)", lower
    )
    if claims_token_valid:
        return False, "claims `infrahubctl info` confirms the token is valid"
    return True, "checks the token or probes a write rather than trusting `info`"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

CHECKS = {
    "docs-fallback": check_docs_fallback,
    "cli-commands-exist": check_cli_commands_exist,
    "python-transform-dry-run": check_python_transform_dry_run,
    "preflight-write-probe": check_preflight_write_probe,
}


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against the output file and return skillgrade JSON."""
    text = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(text)
        except Exception as exc:  # pragma: no cover — defensive
            ok, msg = False, f"Error running check: {exc}"
        if ok:
            passed_count += 1
        entries.append({"name": name, "passed": ok, "message": msg})

    total = len(check_names)
    score = round(passed_count / total, 4) if total > 0 else 0.0
    failed = [e["name"] for e in entries if not e["passed"]]
    if failed:
        details = f"{passed_count}/{total} checks passed. Failed: {', '.join(failed)}"
    else:
        details = f"All {total} checks passed."

    return {"score": score, "details": details, "checks": entries}


if __name__ == "__main__":  # pragma: no cover
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("output.md")
    print(json.dumps(run_checks(list(CHECKS.keys()), out), indent=2))
