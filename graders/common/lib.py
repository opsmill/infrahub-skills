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
# The tree and the code-region scanner live in cli_tree.py, imported here as
# a sibling: the eval harness puts this directory on sys.path, so the
# grader stays standalone while the tree stays written down once.
# scripts/check-cli-invocations.py loads the same module and asks the same
# question of the repository's own prose.
# ---------------------------------------------------------------------------

from cli_tree import invalid_invocations  # noqa: E402


def check_cli_commands_exist(text: str) -> tuple[bool, str]:
    """Every `infrahubctl ...` command in the answer must be a real command.

    Guards the invented-subcommand class directly: a group given a
    subcommand it does not have, or a leaf given a generic verb where its
    positional target belongs. Both read plausibly and both fail on first
    use. graders/common/cli_tree.py holds the tree they are checked against.
    """
    if not text.strip():
        return False, "no output to check"
    if "infrahubctl" not in text:
        return False, "answer names no infrahubctl command at all"
    bad = invalid_invocations(text)
    if bad:
        return False, f"command(s) that do not exist: {sorted(set(bad))}"
    return True, "all infrahubctl commands referenced exist"


# Words that turn a following command mention into a contrast rather than a
# recommendation: "use transform, not render spine_config".
_NEGATED_BEFORE = re.compile(
    r"\b(not|never|instead of|rather than|avoid|don't|do not|isn't|is not|"
    r"wrong|incorrect|won't|will not|fails?)\b[^.\n]{0,40}$"
)


def check_python_transform_dry_run(
    text: str, transform_name: str = "spine_config"
) -> tuple[bool, str]:
    """A Python transform must be dry-run with `transform`, never `render`.

    `render` resolves names against `jinja2_transforms` only, so pointing it
    at a `python_transforms` entry prints "Unable to find <name>", which
    reads as an unregistered transform rather than the wrong command. The
    reader concludes the gate is unavailable and skips it.

    Both tests name the transform, so a bare mention of `infrahubctl
    transform` in a contrast sentence no longer clears the check while the
    answer aims `render` at the same transform.

    The transform name is a check parameter, not a constant: registered as
    `python-transform-dry-run:<name>`, so a second task with a different
    fixture does not have to reuse this one's.
    """
    lower = text.lower()
    # Accept either separator: a model may write spine-config for spine_config.
    named = "[_-]".join(
        re.escape(part) for part in re.split(r"[_-]", transform_name.lower())
    )
    if not re.search(rf"infrahubctl\s+transform\s+{named}", lower):
        return False, "does not aim `infrahubctl transform` at the named Python transform"
    # `render` may legitimately appear to draw the contrast, and the task's
    # own expectations ask for exactly that ("recommends transform, *not*
    # render"). What must not appear is render aimed at the named python
    # transform as a recommendation, so a negated mention is allowed.
    for match in re.finditer(rf"infrahubctl\s+render\s+{named}", lower):
        preceding = lower[max(0, match.start() - 60):match.start()]
        if not _NEGATED_BEFORE.search(preceding):
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
    # The claim has to be affirmative. "A green `info` does not confirm the
    # token is present" is the rule's own sentence, and matching it here
    # failed the best possible answer.
    claims_token_valid = re.search(
        r"info(?![^.\n]{0,80}\b(?:not|never|n't|nothing|no)\b)"
        r"[^.\n]{0,80}(token is valid|validates the token|confirms the token)",
        lower,
    )
    if claims_token_valid:
        return False, "claims `infrahubctl info` confirms the token is valid"
    return True, "probes a write and states that a green `info` is not write authorisation"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------

_GENERATOR_INVOCATION = re.compile(
    r"infrahubctl\s+generator\s+([a-z0-9][\w.-]*)((?:\s+[^\s`]+)*)", re.IGNORECASE
)
def _positional_args(rest: str) -> list[str]:
    """Tokens after the generator name that are not flags or flag values.

    A flag is assumed to take a value, so `--branch dry-run` consumes both.
    That over-consumes after a boolean flag, which costs a missed check
    rather than a false failure — the safer direction for a gate.
    """
    tokens = rest.split()
    out: list[str] = []
    skip = False
    for token in tokens:
        if skip:
            skip = False
            continue
        if token.startswith("-"):
            skip = "=" not in token
            continue
        out.append(token)
    return out


def check_generator_target_is_key_value(text: str) -> tuple[bool, str]:
    """A generator target is a query variable, never a bare id.

    `infrahubctl generator` parses everything after the name as `key=value`
    and drops a token without an `=`. With no variables left it falls back
    to running the generator over every member of the target group, so a
    bare id is a mass write rather than the single-target run the author
    intended. The run also has to name a branch, because it writes.
    """
    if not text.strip():
        return False, "no output to check"
    invocations = _GENERATOR_INVOCATION.findall(text)
    if not invocations:
        return False, "answer names no `infrahubctl generator <name> ...` invocation"
    for name, rest in invocations:
        args = _positional_args(rest)
        if not args:
            return False, f"`generator {name}` passes no target at all"
        bare = [a for a in args if "=" not in a]
        if bare:
            return False, (
                f"`generator {name}` passes a bare token {bare!r}; a target is "
                "a `key=value` query variable, and a bare token is dropped"
            )
        if "--branch" not in rest:
            return False, f"`generator {name}` runs with no --branch, so it writes to main"
    return True, "generator target is a key=value variable on a named branch"


# A name may carry colon-separated arguments, e.g.
# `python-transform-dry-run:spine_config`, so a check that depends on a task
# fixture is not pinned to one task by its registry entry.
CHECKS = {
    "docs-fallback": check_docs_fallback,
    "cli-commands-exist": check_cli_commands_exist,
    "python-transform-dry-run": check_python_transform_dry_run,
    "preflight-write-probe": check_preflight_write_probe,
    "generator-target-is-key-value": check_generator_target_is_key_value,
}


def _dispatch(name: str, text: str) -> tuple[bool, str]:
    base, _, args = name.partition(":")
    fn = CHECKS[base]
    return fn(text, *args.split(":")) if args else fn(text)


def run_checks(check_names: list[str], output_path: Path) -> dict:
    """Run named checks against the output file and return skillgrade JSON."""
    text = load_output(output_path)

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        try:
            ok, msg = _dispatch(name, text)
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
