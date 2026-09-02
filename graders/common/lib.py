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
# prints, which is the outcome the rules exist to change.
#
# Keep _CLI_SDK_VERSION, the tree below, and the same three constants in
# scripts/check-cli-invocations.py in step. When the CLI changes, both copies
# move together and the commit says which SDK version they were read from.
# ---------------------------------------------------------------------------

_CLI_SDK_VERSION = "1.23.1"

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

# Words that follow `infrahubctl` in a heading or a table cell without being
# a command. Same list as the script's PROSE_ALLOWLIST.
_CLI_PROSE_ALLOWLIST: set[str] = {"available", "commands", "first"}

_CLI_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_CLI_SPAN = re.compile(r"`([^`\n]+)`")


def _cli_code_regions(text: str) -> str:
    """Return only the parts of an answer that read as code.

    A model answer is mostly prose, and prose that happens to follow the
    word `infrahubctl` ("infrahubctl reads the token from the environment")
    is not an invocation. Scanning fenced blocks and inline code spans keeps
    the check on what a reader would paste into a shell, so a correct answer
    is not failed for an ordinary sentence. An invented command written as
    bare prose is missed; the LLM assertion on the same task covers that.
    """
    regions = _CLI_FENCE.findall(text)
    regions.extend(_CLI_SPAN.findall(_CLI_FENCE.sub("\n", text)))
    return "\n".join(regions)


def check_cli_commands_exist(text: str) -> tuple[bool, str]:
    """Every `infrahubctl ...` command in the answer must be a real command.

    Guards the invented-subcommand class directly: `schema validate`,
    `check run`, `generator list`, `import load` all read plausibly and all
    fail on first use.
    """
    bad: list[str] = []
    for first, second in _CLI_INVOCATION.findall(_cli_code_regions(text)):
        if first in _CLI_PROSE_ALLOWLIST:
            continue
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

    Both tests name the transform, so a bare mention of `infrahubctl
    transform` in a contrast sentence no longer clears the check while the
    answer aims `render` at the same transform. The fixture name comes from
    the `common-dry-run-python-transform` task in eval.yaml; a new task
    reusing this check has to use the same one.
    """
    lower = text.lower()
    # Accept either separator: a model may write spine-config for spine_config.
    named = r"spine[_-]config"
    if not re.search(rf"infrahubctl\s+transform\s+{named}", lower):
        return False, "does not aim `infrahubctl transform` at the named Python transform"
    # `render` may legitimately appear to draw the contrast; what must not
    # appear is render aimed at the named python transform.
    if re.search(rf"infrahubctl\s+render\s+{named}", lower):
        return False, "recommends `infrahubctl render` for a python_transforms entry"
    return True, "uses `infrahubctl transform` for the named Python transform"


# The probe is the create/delete *pair*. `branch create` on its own is
# handed to the model by the task prompt ("I am about to run `infrahubctl
# branch create` ..."), so an answer that restates the user's plan would
# score on it. `branch delete` appears nowhere in the prompt.
_WRITE_PROBE_CREATE = re.compile(r"branch\s+create\b")
_WRITE_PROBE_DELETE = re.compile(r"branch\s+delete\b")

# The answer must also say, in words, that a green connectivity result is
# not clearance to write. Any one of these forms counts.
_NOT_PROOF_PATTERNS = [
    r"(does not|doesn't|do not|don't|never)[^.\n]{0,70}"
    r"(prove|proof|confirm|guarantee|establish|mean you have)"
    r"[^.\n]{0,70}(write|token|auth|permission)",
    r"(not|no)\s+proof[^.\n]{0,70}(write|token|auth|permission)",
    r"green[^.\n]{0,90}(not enough|insufficient|not sufficient|not clearance|proves nothing)",
    r"reads?\s+(are|is)\s+(served\s+)?anonymous",
    r"anonymous(ly)?[^.\n]{0,70}read",
]


def check_preflight_write_probe(text: str) -> tuple[bool, str]:
    """A pre-flight before a write must not rest on `infrahubctl info` alone.

    With no token set, `info` skips the user lookup entirely and reports a
    green status, so it passes on exactly the misconfiguration it exists to
    catch. Two things must be present, and neither is available by echoing
    the prompt: the create *and* delete pair that probes a write, and an
    explicit statement that a green result is not write authorisation. An
    answer that says "your green `info` means you are good to go" fails on
    both.
    """
    lower = text.lower()
    if not (_WRITE_PROBE_CREATE.search(lower) and _WRITE_PROBE_DELETE.search(lower)):
        return False, "no write probe: expected a throwaway `branch create` and `branch delete` pair"
    if not any(re.search(p, lower) for p in _NOT_PROOF_PATTERNS):
        return False, "does not state that a green `infrahubctl info` is not proof of write access"
    claims_token_valid = re.search(
        r"info[^.\n]{0,80}(token is valid|validates the token|confirms the token)", lower
    )
    if claims_token_valid:
        return False, "claims `infrahubctl info` confirms the token is valid"
    return True, "probes a write and states that a green `info` is not write authorisation"


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
