"""Shared grader library for infrahub-managing-checks skill evaluations.

The managing-checks skill produces three artifacts: a `.gql` query, a
Python class, and a `.infrahub.yml` registration. The eval prompt asks
the model to save a single combined `output.yml` representing the
`.infrahub.yml` content; assertions focus on the registration shape,
since that is where the most common confusion (the rejected `query:`
field on `check_definitions`) lives.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import shlex
import sys
import textwrap
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# Allowed fields per InfrahubCheckDefinitionConfig (Pydantic extra="forbid")
# ---------------------------------------------------------------------------

ALLOWED_CHECK_DEF_FIELDS: set[str] = {
    "name",
    "file_path",
    "class_name",
    "targets",
    "parameters",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_output(path: Path) -> tuple[dict, str]:
    """Load a YAML file and return (parsed_dict, raw_text)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return {}, ""
    try:
        parsed = yaml.safe_load(raw) or {}
    except yaml.YAMLError:
        parsed = {}
    return parsed, raw


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def load_output_py(path: Path) -> tuple[ast.Module | None, str]:
    """Load a Python check file and return ``(parsed_tree, raw_text)``.

    ``(None, "")`` when absent, ``(None, raw)`` on a syntax error, so the
    checks below can distinguish "no file" from "unparseable file".
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None, ""
    try:
        return ast.parse(raw), raw
    except SyntaxError:
        return None, raw


# ---------------------------------------------------------------------------
# Error-surface checks
#
# The server hard-codes status_code=200 on every executed GraphQL request and
# puts rejections in the body's `errors` array, so branching on the status
# code fails OPEN: the check passes on the case it exists to catch. The SDK's
# execute_graphql already raises GraphQLError when `"errors" in response`, so
# the fix is to use it. Verified against Infrahub 1.11.0 / SDK 1.23.1.
# ---------------------------------------------------------------------------

_RAW_HTTP_MODULES = frozenset({"httpx", "requests", "aiohttp", "urllib"})


def _raw_http_modules_used(tree: ast.Module) -> list[str]:
    """Names of raw HTTP clients actually imported or called, ignoring prose.

    AST-only on purpose: a compliant check that *names* the antipattern in a
    comment or docstring, which both the rule and the eval prompt invite, must
    not be failed for describing it.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found.add(node.value.id)
    return sorted(found & _RAW_HTTP_MODULES)


def _calls_execute_graphql(tree: ast.Module) -> bool:
    """True when `execute_graphql` is called somewhere in the code itself."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "execute_graphql":
            return True
    return False


def _references_status_code(node: ast.AST) -> bool:
    """True when an expression reads a `status_code` attribute or name."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == "status_code":
            return True
        if isinstance(sub, ast.Name) and sub.id == "status_code":
            return True
    return False


def _branches_on_status_code(tree: ast.Module) -> bool:
    """True when control flow or a comparison turns on an HTTP status code."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp, ast.While)) and _references_status_code(node.test):
            return True
        if isinstance(node, ast.Assert) and _references_status_code(node.test):
            return True
        if isinstance(node, ast.Compare) and _references_status_code(node):
            return True
    return False


def _call_name(call: ast.Call) -> str:
    """The bare callee name of a call, whether plain or attribute access."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return getattr(func, "id", "")


def _handler_names(handler: ast.ExceptHandler) -> list[str]:
    """Exception names an `except` clause catches; `bare except` when untyped."""
    node = handler.type
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Tuple):
        return [
            e.id if isinstance(e, ast.Name) else getattr(e, "attr", "?") for e in node.elts
        ]
    if node is None:
        return ["bare except"]
    return []


def _calls_log_error(node: ast.AST) -> bool:
    """True when `log_error` is called anywhere beneath this node."""
    return any(
        isinstance(sub, ast.Call) and _call_name(sub) == "log_error" for sub in ast.walk(node)
    )


def check_uses_sdk_execute_graphql(
    _config: dict | None = None, *, tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Follow-up calls must go through the SDK client, which raises on errors."""
    if not py_raw:
        return False, "no Python source found"
    if tree is None:
        return False, "check file has a syntax error"
    if _calls_execute_graphql(tree):
        raw_http = _raw_http_modules_used(tree)
        if raw_http and _raw_http_requests_made(tree):
            return False, (
                f"calls execute_graphql but also sends raw HTTP ({raw_http}); "
                "the raw path does not raise on a GraphQL error"
            )
        return True, "uses self.client.execute_graphql"
    # api-error-surfaces.md sanctions a raw-HTTP fallback, provided it
    # inspects the response body for `errors` rather than the status code.
    # Rejecting it outright made the grader forbid what the rule allows.
    if _inspects_graphql_errors_payload(tree):
        return True, (
            "uses raw HTTP but inspects the response body for `errors`, which "
            "is the fail-closed fallback the rule permits"
        )
    return False, (
        "does not call self.client.execute_graphql, and does not inspect the "
        "response body for an `errors` key either, so a rejection is invisible"
    )


def check_no_status_code_branch(
    _config: dict | None = None, *, tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """Branching on an HTTP status code to detect a rejection fails open."""
    if not py_raw:
        return False, "no Python source found"
    if tree is None:
        return False, "check file has a syntax error"
    if _branches_on_status_code(tree):
        return False, (
            "branches on status_code; every executed GraphQL request returns "
            "200 even when the body carries errors"
        )
    return True, "does not branch on a status code"


# HTTP verbs, as method or function names. `import urllib.parse` to build a
# URL is not a raw request; `urllib.request.urlopen(...)` is.
_HTTP_REQUEST_CALLS = {
    "get", "post", "put", "patch", "delete", "head", "options", "request",
    "urlopen", "send", "stream",
}


def _raw_http_requests_made(tree: ast.Module) -> list[str]:
    """Calls that actually send a request through a raw HTTP client."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _HTTP_REQUEST_CALLS:
            continue
        receiver = node.func.value
        while isinstance(receiver, ast.Attribute):
            receiver = receiver.value
        if isinstance(receiver, ast.Name) and receiver.id in _RAW_HTTP_MODULES:
            found.add(ast.unparse(node.func))
    return sorted(found)


def _inspects_graphql_errors_payload(tree: ast.Module) -> bool:
    """True when the code reads an `errors` key out of a response body.

    api-error-surfaces.md sanctions a raw-HTTP fallback on exactly this
    condition: the status code is always 200, so the body's `errors` key is
    what a rejection looks like.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "errors":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "errors":
            return True
    return False


def _logs_error_on_payload_errors(tree: ast.Module) -> bool:
    """True when a branch testing for `errors` in the body calls log_error."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if not _inspects_graphql_errors_payload(node.test):
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Call) and _call_name(call) == "log_error":
                return True
    return False


def _try_blocks_calling_execute_graphql(tree: ast.Module) -> list[ast.Try]:
    """`try` statements whose body reaches `execute_graphql`."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and any(
            _calls_execute_graphql(ast.Module(body=[stmt], type_ignores=[]))
            for stmt in node.body
        ):
            out.append(node)
    return out


def check_catches_graphql_error(
    _config: dict | None = None, *, tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """A rejection must be handled as a raised GraphQLError, and logged as an error."""
    if tree is None:
        return False, "check file missing or has a syntax error"
    handlers = [n for n in ast.walk(tree) if isinstance(n, ast.ExceptHandler)]
    if not handlers:
        # The SDK client raises, so an SDK-based check needs a handler. A
        # raw-HTTP check has nothing to catch: for it, the fail-closed shape
        # api-error-surfaces.md sanctions is testing the body for `errors`.
        if not _calls_execute_graphql(tree) and _inspects_graphql_errors_payload(tree):
            if _logs_error_on_payload_errors(tree):
                return True, (
                    "raw-HTTP path: detects a rejection from the response body's "
                    "`errors` key and logs an error"
                )
            return False, (
                "reads the response body's `errors` key but never calls "
                "log_error on it, so the check still passes"
            )
        return False, "no except handler; a rejection raises GraphQLError"

    names: list[str] = []
    graphql_handlers: list[ast.ExceptHandler] = []
    for handler in handlers:
        caught = _handler_names(handler)
        names.extend(caught)
        if "GraphQLError" in caught:
            graphql_handlers.append(handler)

    if not graphql_handlers:
        return False, f"catches {names} but not GraphQLError"
    # Only a broad handler that actually wraps the GraphQL call reintroduces
    # fail-open. Scanning the whole module failed a correct check for an
    # unrelated `try: json.loads(...) / except Exception:`.
    graphql_tries = _try_blocks_calling_execute_graphql(tree)
    # If nothing identifiably wraps the GraphQL call, fall back to the whole
    # module: a broad handler somewhere is still the likely cause.
    scoped = [h for t in graphql_tries for h in t.handlers] or handlers
    broad_over_graphql = [
        caught
        for handler in scoped
        for caught in [_handler_names(handler)]
        if "Exception" in caught or "bare except" in caught
    ]
    if broad_over_graphql:
        return False, (
            f"catches {broad_over_graphql} around execute_graphql; a broad "
            "handler there reintroduces fail-open"
        )
    if not any(_calls_log_error(h) for h in graphql_handlers):
        return False, "catches GraphQLError but never calls log_error, so the check still passes"
    return True, "catches GraphQLError and logs an error"


def check_separate_local_bounds_branch(
    _config: dict | None = None, *, tree: ast.Module | None = None, py_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """A locally-detectable bad value needs its own branch: only a rejection raises.

    Passing requires a `log_error` reached without an exception handler, so the
    out-of-range case is reported by the check's own logic rather than being
    left to a server round trip that never raises for it.
    """
    if not py_raw:
        return False, "no Python source found"
    if tree is None:
        return False, "check file has a syntax error"

    handler_calls = {
        id(call)
        for handler in ast.walk(tree)
        if isinstance(handler, ast.ExceptHandler)
        for call in ast.walk(handler)
        if isinstance(call, ast.Call)
    }
    # The log_error has to sit on a test the check made itself, not merely
    # outside an except handler. Without that, the prompt's own
    # `if resp.status_code == 200: ... else: log_error(...)` antipattern
    # scored this, the task's most distinctive assertion.
    #
    # "A test the check made itself" is a comparison OR a predicate it calls:
    # api-error-surfaces.md writes the bound test as `if not _in_bounds(value)`,
    # which carries no ast.Compare at all, so requiring one failed the rule's
    # own example.
    guarded: list[str] = []
    for branch in ast.walk(tree):
        if not isinstance(branch, ast.If):
            continue
        test = branch.test
        if not any(isinstance(n, (ast.Compare, ast.Call)) for n in ast.walk(test)):
            continue
        if _branches_on_status_code(branch):
            continue  # a status code is not a locally-detectable bad value
        for call in ast.walk(branch):
            if (
                isinstance(call, ast.Call)
                and _call_name(call) == "log_error"
                and id(call) not in handler_calls
            ):
                guarded.append(ast.unparse(test)[:60])
                break
    if not guarded:
        return False, (
            "no log_error sits on a test the check made itself (a comparison "
            "or its own predicate); the locally-detectable out-of-range value "
            "needs its own branch, not an except handler and not a "
            "status-code test"
        )
    return True, f"reports the locally-detectable value on its own test: {guarded[:2]}"


# ---------------------------------------------------------------------------
# Shared-module checks
#
# A module used by more than one artifact type cannot be reached with a
# relative import, so it has to be installed into the worker image. The two
# flags that decide whether that image works are UV_PROJECT_ENVIRONMENT (the
# base image's virtualenv) and --inexact (without it `uv sync` removes the
# Infrahub install). Verified against Infrahub 1.11.0 / SDK 1.23.1.
# ---------------------------------------------------------------------------

_WATCHABLE_SECTIONS = ("python_transforms", "generator_definitions")

# Imports that are not the shared package under any circumstances. The old
# exclusion list held three names, so `import os` satisfied "an absolute
# import of the shared package".
_STDLIB_AND_SDK = frozenset(sys.stdlib_module_names) | {
    "infrahub_sdk", "__future__", "httpx", "requests", "yaml", "pydantic",
}


def _dockerfile_instructions(raw: str) -> str:
    """A Dockerfile with its `#` comment lines removed, continuations joined.

    patterns-shared-module.md teaches the reader to annotate the wrong form
    with a `# WRONG: ...` comment, so matching raw text failed the correct
    answer on its own documentation and passed a pip-installing image whose
    only mention of `--inexact` was in a comment.
    """
    lines = [
        line for line in raw.splitlines()
        if not line.lstrip().startswith("#")
    ]
    joined: list[str] = []
    for line in lines:
        stripped = line.rstrip()
        if joined and joined[-1].endswith("\\"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + stripped.lstrip()
        else:
            joined.append(stripped)
    return "\n".join(joined)


def _declared_package(config: dict, dockerfile_raw: str, py_raw: str) -> str | None:
    """The shared package name, from the `watch:` paths the config declares.

    Everything in this pattern has to name the same package: the check
    imports it, the image installs it, and `watch:` points at its source.
    Without a shared anchor each check passes independently on unrelated
    inputs -- `import json`, a pip Dockerfile, and `watch: {files: []}`
    scored 4/4.
    """
    for section in _WATCHABLE_SECTIONS:
        for entry in config.get(section) or []:
            if not isinstance(entry, dict):
                continue
            watch = entry.get("watch")
            if not isinstance(watch, dict):
                continue
            for path in watch.get("files") or []:
                name = str(path).rstrip("/").rsplit("/", 1)[-1]
                if name and not name.startswith("."):
                    return name.removesuffix(".py")
    return None


def check_shared_module_absolute_import(
    _config: dict | None = None,
    *,
    tree: ast.Module | None = None,
    py_raw: str = "",
    dockerfile_raw: str = "",
    **_: Any,
) -> tuple[bool, str]:
    """The shared module is imported absolutely, never relatively or via sys.path.

    The imported name has to be the package the rest of the layout declares,
    not any absolute import at all: `import json` alone was satisfying this.
    """
    if not py_raw:
        return False, "no Python source found"
    if tree is None:
        return False, "check file has a syntax error"

    relative = [
        f"{'.' * node.level}{node.module or ''}"
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    ]
    if relative:
        return False, (
            f"imports {relative} relatively; a relative import cannot reach a "
            "module outside this artifact's own directory"
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "path":
            if isinstance(node.value, ast.Name) and node.value.id == "sys":
                return False, "edits sys.path; the worker runs from a different directory"

    absolute = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module
    }
    absolute |= {
        alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names
    }
    shared = absolute - _STDLIB_AND_SDK
    if not shared:
        return False, (
            "no absolute import of a shared package; only the SDK and the "
            "standard library are imported"
        )
    package = _declared_package(_config or {}, dockerfile_raw, py_raw)
    if package and package not in shared:
        return False, (
            f"imports {sorted(shared)}, but the layout declares the shared "
            f"package as {package!r} under `watch:`; the check has to import "
            "the package the image installs"
        )
    return True, f"imports {sorted(shared)} absolutely"


def check_dockerfile_targets_base_venv(
    _config: dict | None = None, *, dockerfile_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """The install must target the base image's virtualenv, not a fresh one."""
    if not dockerfile_raw:
        return False, "no Dockerfile found"
    instructions = _dockerfile_instructions(dockerfile_raw)
    if not re.search(r"UV_PROJECT_ENVIRONMENT\s*=?\s*[\"']?/\.venv", instructions):
        return False, (
            "does not set UV_PROJECT_ENVIRONMENT=/.venv; uv would build its own "
            "virtualenv and the workers would not see the package"
        )
    return True, "installs into the base image's /.venv"


def check_dockerfile_uv_sync_inexact(
    _config: dict | None = None, *, dockerfile_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """`uv sync` without `--inexact` removes the Infrahub install from the image."""
    if not dockerfile_raw:
        return False, "no Dockerfile found"
    syncs = re.findall(r"uv\s+sync[^\n]*", _dockerfile_instructions(dockerfile_raw))
    if not syncs:
        return False, "no `uv sync` line installing the package"
    bare = [line for line in syncs if "--inexact" not in line]
    if bare:
        return False, f"`uv sync` without --inexact ({bare[0].strip()}) wipes the base environment"
    return True, "uv sync carries --inexact"


def check_watch_declares_shared_package(config: dict, **_: Any) -> tuple[bool, str]:
    """Artifacts importing the installed package declare it under `watch:`.

    An installed package is invisible to Infrahub's dependency detection, so
    without this the artifact does not regenerate when the shared logic changes.
    """
    present = [
        (section, entry)
        for section in _WATCHABLE_SECTIONS
        for entry in (config.get(section) or [])
        if isinstance(entry, dict)
    ]
    if not present:
        return False, f"no {' or '.join(_WATCHABLE_SECTIONS)} entries to declare a dependency on"

    missing = [f"{section}:{entry.get('name', '?')}" for section, entry in present if "watch" not in entry]
    if missing:
        return False, f"no `watch:` on {missing}; the artifact will not regenerate"

    malformed = [
        f"{section}:{entry.get('name', '?')}"
        for section, entry in present
        if not isinstance(entry["watch"], dict)
        or set(entry["watch"]) - {"files"}
    ]
    if malformed:
        return False, f"`watch:` on {malformed} is not a mapping with only a `files` key"

    # `watch: {}` and `watch: {files: []}` are valid YAML and a legitimate
    # answer in general -- they record that the author checked -- but they
    # declare no dependency, which is the failure this check exists to catch.
    # They also erase the anchor `_declared_package` derives, so accepting
    # them let `import netdomain` plus an empty `watch:` score 4/4.
    empty = [
        f"{section}:{entry.get('name', '?')}"
        for section, entry in present
        if not entry["watch"].get("files")
    ]
    if empty:
        return False, (
            f"`watch:` on {empty} lists no files; an empty `files` declares no "
            "dependency, so the artifact still will not regenerate when the "
            "shared package changes"
        )
    return True, f"all {len(present)} watchable entries declare `watch:` with files"


def check_check_definitions_present(config: dict, **_: Any) -> tuple[bool, str]:
    """`.infrahub.yml` declares at least one entry under check_definitions."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    names = [d.get("name", "?") for d in defs]
    return True, f"check_definitions: {', '.join(names)}"


def check_no_query_field_in_check_def(config: dict, **_: Any) -> tuple[bool, str]:
    """No entry under check_definitions contains a `query:` key.

    `InfrahubCheckDefinitionConfig` uses Pydantic `extra="forbid"`, so
    `query:` here causes the repository config to fail to load. The
    query is bound on the Python class via the `query = "..."`
    attribute, which references a name under top-level `queries:`.
    """
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        if "query" in entry:
            bad.append(entry.get("name", "?"))
    if bad:
        return False, f"Forbidden `query:` field on check_definitions[]: {', '.join(bad)}"
    return True, "No `query:` field on any check_definitions entry"


def check_only_allowed_fields_in_check_def(config: dict, **_: Any) -> tuple[bool, str]:
    """Each check_definitions entry uses only allowed fields."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        unknown = set(entry.keys()) - ALLOWED_CHECK_DEF_FIELDS
        if unknown:
            name = entry.get("name", "?")
            bad.append(f"{name}: {', '.join(sorted(unknown))}")
    if bad:
        return False, f"Unknown fields under check_definitions: {'; '.join(bad)}"
    return True, "All check_definitions entries use only allowed fields"


def check_queries_section_present(config: dict, **_: Any) -> tuple[bool, str]:
    """Top-level queries: section declares at least one query.

    The query that backs each check must be registered here; the Python
    class's `query = "..."` references this name.
    """
    queries = config.get("queries") or []
    if not queries:
        return False, "No top-level `queries:` entries found"
    names = [q.get("name", "?") for q in queries if isinstance(q, dict)]
    return True, f"queries: {', '.join(names)}"


def check_check_def_required_fields(config: dict, **_: Any) -> tuple[bool, str]:
    """Each check_definitions entry has the required fields name + file_path."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        missing = []
        if not name:
            missing.append("name")
        if not entry.get("file_path"):
            missing.append("file_path")
        if missing:
            bad.append(f"{name or '<unnamed>'}: {', '.join(missing)}")
    if bad:
        return False, f"check_definitions missing required fields: {'; '.join(bad)}"
    return True, "All check_definitions entries have name and file_path"


def check_targeted_has_targets_and_parameters(
    config: dict, **_: Any
) -> tuple[bool, str]:
    """When a check is described as targeted, it declares targets and parameters."""
    defs = config.get("check_definitions") or []
    if not defs:
        return False, "No check_definitions entries found"
    found_targeted = False
    bad: list[str] = []
    for entry in defs:
        if not isinstance(entry, dict):
            continue
        if "targets" in entry:
            found_targeted = True
            name = entry.get("name", "?")
            if not entry.get("parameters"):
                bad.append(f"{name}: missing parameters")
    if not found_targeted:
        return False, "No targeted check_definitions entry found"
    if bad:
        return False, "; ".join(bad)
    return True, "All targeted check_definitions entries declare parameters"


# ---------------------------------------------------------------------------
# Shell script checks: re-validating open proposed changes
# ---------------------------------------------------------------------------
#
# A proposed change runs its checks with the code at the repository commit
# recorded on its source branch. On a branch synced with Git, neither
# `infrahubctl branch rebase` nor `CoreProposedChangeRunCheck` moves that
# commit; pushing main into the branch's own Git branch does, and so does
# opening a new branch and proposed change. The script is tokenized with
# shlex, so comments, prose and echoed strings do not count as commands.

# A fence may be indented under a list item, and closes on a run of the same
# character at least as long as the one that opened it.
_FENCE_RE = re.compile(r"^[ \t]*((`|~)\2{2,})[^\n]*\n(.*?)^[ \t]*\1\2*[ \t]*$", re.S | re.M)
_HEREDOC_RE = re.compile(r"(?<!<)<<(?!<)-?[ \t]*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_SHELL_PUNCT = ";&|()<>\n"
_SHELL_KEYWORDS = {
    "if", "then", "elif", "else", "while", "until", "do", "!", "{", "}",
    "time", "exec", "command", "nohup", "export", "local", "readonly",
}
# Wrappers peeled off before argv[0], each with the options that take a value.
_PREFIX_WRAPPERS: dict[str, set[str]] = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-U"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
}
_RUN_WRAPPERS: dict[str, set[str]] = {
    "uv": {"--project", "--directory", "--python", "-p", "--with", "--group", "--extra", "--package"},
    "poetry": {"-C", "--directory", "-P", "--project"},
    "pipx": {"--spec", "--python"},
}

# The infrahubctl tree is the one the CLI gate pins, loaded by path (the eval
# harness puts only this directory on sys.path), so this grader and
# scripts/check-cli-invocations.py cannot disagree about it.
_TREE_SPEC = importlib.util.spec_from_file_location(
    "managing_checks_cli_tree", Path(__file__).resolve().parent.parent / "common" / "cli_tree.py"
)
_cli_tree = importlib.util.module_from_spec(_TREE_SPEC)
_TREE_SPEC.loader.exec_module(_cli_tree)
_BRANCH_GROUP = "branch"
_BRANCH_CREATE = "create"
_BRANCH_REBASE = "rebase"
assert {_BRANCH_CREATE, _BRANCH_REBASE} <= _cli_tree.GROUPS[_BRANCH_GROUP], (
    "graders/common/cli_tree.py no longer lists `infrahubctl branch create|rebase`"
)
_SHELL_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
_SHELL_VAR_RE = re.compile(r"\$\{?([A-Za-z_][A-Za-z0-9_]*|[0-9@*])")
_PARAM_DEFAULT_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*):?[-=]([^}]*)\}")
_DEFAULT_BRANCHES = {"main", "master"}
_GIT_GLOBAL_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
_GIT_VALUE_OPTS: dict[str, set[str]] = {
    "merge": {"-m", "-F", "--file", "-s", "--strategy", "-X", "--strategy-option"},
    "rebase": {"--onto", "-s", "--strategy", "-X", "--strategy-option", "-x", "--exec"},
    "pull": {"-s", "--strategy", "-X", "--strategy-option", "--depth", "--upload-pack"},
    "push": {"-o", "--push-option", "--repo", "--receive-pack", "--exec"},
    "checkout": {"-b", "-B", "--orphan", "--conflict"},
    "switch": {"-c", "-C", "--orphan", "--conflict"},
    "worktree": {"-b", "-B", "--reason"},
    "clone": {
        "-b", "--branch", "-o", "--origin", "--depth", "-c", "--config", "--reference",
        "-u", "--upload-pack", "--separate-git-dir", "-j", "--jobs", "--filter",
    },
}
# Programs that send a GraphQL document or SDK call to Infrahub. A mutation name
# counts only where one of these, or a script function that calls one, sends it.
_SENDERS = {"curl", "wget", "http", "https", "xh", "infrahubctl"}
_BRANCH_CREATE_GQL_RE = re.compile(r"\bBranchCreate\s*\(|\.branch\.create\s*\(")
_PC_CREATE_GQL_RE = re.compile(
    r"\bCoreProposedChangeCreate\s*\(|\bcreate\s*\(\s*(?:kind\s*=\s*)?[\"']CoreProposedChange[\"']"
)


def _shell_script_text(raw: str) -> str:
    """The script itself: every fenced block when the answer is fenced, else the file."""
    blocks = [m.group(3) for m in _FENCE_RE.finditer(raw)]
    return "\n".join(blocks) if blocks else raw


def _split_heredocs(text: str) -> tuple[list[str], list[tuple[int, str, int]]]:
    """Script lines with heredoc bodies blanked, plus each body line.

    Each body line comes with its own index and the index of the line that
    opened the heredoc. A heredoc body is data (a GraphQL document, a Python
    snippet), not shell, so tokenizing it as commands would fabricate calls and
    trip on its quotes.
    """
    lines = text.split("\n")
    shell: list[str] = []
    bodies: list[tuple[int, str, int]] = []
    pending: list[tuple[str, int]] = []
    for idx, line in enumerate(lines):
        if pending:
            bodies.append((idx, line, pending[0][1]))
            shell.append("")
            if line.strip() == pending[0][0]:
                pending.pop(0)
            continue
        shell.append(line)
        if not line.lstrip().startswith("#"):
            pending.extend((m.group(2), idx) for m in _HEREDOC_RE.finditer(line))
    return shell, bodies


def _shell_tokens(line: str) -> list[str]:
    """Tokens of a logical line; a newline outside quotes is an operator token."""
    lex = shlex.shlex(line, posix=True, punctuation_chars=_SHELL_PUNCT)
    lex.whitespace = " \t\r"
    lex.whitespace_split = True
    lex.commenters = "#"
    return list(lex)


def _logical_lines(shell_lines: list[str]) -> list[tuple[int, list[str]]]:
    """Tokenized logical lines, each with the index of the line it starts on.

    Backslash continuations are joined, and a line whose quote is still open is
    joined with the following lines until it closes (a multi-line GraphQL string
    assigned to a variable). A quote that never closes drops that line only.
    """
    joined: list[tuple[int, str]] = []
    buf, start = "", 0
    for idx, line in enumerate(shell_lines):
        if not buf:
            start = idx
        if line.endswith("\\"):
            buf += line[:-1]  # the shell joins a continuation with no separator
            continue
        joined.append((start, buf + line))
        buf = ""
    if buf:
        joined.append((start, buf))

    out: list[tuple[int, list[str]]] = []
    i = 0
    while i < len(joined):
        start, text = joined[i]
        j = i
        while True:
            try:
                out.append((start, _shell_tokens(text)))
                i = j + 1
                break
            except ValueError:
                j += 1
                if j >= len(joined):
                    i += 1
                    break
                text = text + "\n" + joined[j][1]
    return out


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    """Split a logical line on shell operators, dropping redirections."""
    segments: list[list[str]] = [[]]
    k = 0
    while k < len(tokens):
        tok = tokens[k]
        if tok and set(tok) <= set(_SHELL_PUNCT):
            if "<" in tok or ">" in tok:
                if segments[-1] and segments[-1][-1].isdigit():
                    segments[-1].pop()
                k += 2  # the operator and its target
                continue
            segments.append([])
            k += 1
            continue
        segments[-1].append(tok)
        k += 1
    return [seg for seg in segments if seg]


def _peel(seg: list[str], assigns: dict[str, list[str]]) -> list[str]:
    """The argv a simple command runs, after keywords, assignments and wrappers.

    Peels `VAR=value`, shell keywords, `sudo` and `env` with their options, and
    `uv|poetry|pipx run` with theirs, so argv[0] is the program that runs.
    """
    i = 0
    while i < len(seg):
        tok = seg[i]
        m = _SHELL_ASSIGN_RE.match(tok)
        if m:
            assigns.setdefault(m.group(1), []).append(m.group(2))
            i += 1
        elif tok in _SHELL_KEYWORDS:
            i += 1
        elif tok in _PREFIX_WRAPPERS:
            opts = _PREFIX_WRAPPERS[tok]
            i += 1
            while i < len(seg) and seg[i].startswith("-"):
                if seg[i] == "--":
                    i += 1
                    break
                i += 2 if seg[i] in opts else 1
        elif tok in _RUN_WRAPPERS:
            opts = _RUN_WRAPPERS[tok]
            j = i + 1
            while j < len(seg) and seg[j].startswith("-"):
                j += 2 if seg[j] in opts else 1
            if j < len(seg) and seg[j] == "run":
                j += 1
                while j < len(seg) and seg[j].startswith("-"):
                    j += 2 if seg[j] in opts else 1
                i = j
            else:
                break
        else:
            break
    return seg[i:]


# Builtins that bind their operands, with the options that take a value.
_BINDING_BUILTINS: dict[str, set[str]] = {
    "read": {"-d", "-i", "-n", "-N", "-p", "-t", "-u"},
    "mapfile": {"-d", "-n", "-O", "-s", "-u", "-C", "-c"},
    "readarray": {"-d", "-n", "-O", "-s", "-u", "-C", "-c"},
}


def _bound_vars(argv: list[str], bound: set[str]) -> None:
    """Record the names a `for`, `select`, `read` or `mapfile` binds at run time."""
    if not argv:
        return
    if argv[0] in {"for", "select"} and len(argv) > 1:
        bound.add(argv[1])
    elif argv[0] in _BINDING_BUILTINS:
        value_opts = _BINDING_BUILTINS[argv[0]]
        j = 1
        while j < len(argv):
            a = argv[j]
            if a == "-a" and j + 1 < len(argv):  # read -a NAME
                bound.add(argv[j + 1])
                j += 2
            elif a.startswith("-"):
                j += 2 if a in value_opts else 1
            else:
                bound.add(a)
                j += 1


def _positionals(args: list[str], value_opts: set[str]) -> list[str]:
    out: list[str] = []
    j = 0
    while j < len(args):
        a = args[j]
        if a == "--":
            out.extend(args[j + 1 :])
            break
        if a.startswith("-") and len(a) > 1:
            j += 2 if a in value_opts else 1
            continue
        out.append(a)
        j += 1
    return out


def _option_value(args: list[str], names: set[str]) -> str | None:
    for j, a in enumerate(args):
        if a in names and j + 1 < len(args):
            return args[j + 1]
        for n in names:
            if n.startswith("--") and a.startswith(n + "="):
                return a[len(n) + 1 :]
    return None


def _git_subcommand(argv: list[str]) -> tuple[str | None, list[str]]:
    if not argv or argv[0].rsplit("/", 1)[-1] != "git":
        return None, []
    j = 1
    while j < len(argv) and argv[j].startswith("-"):
        j += 2 if argv[j] in _GIT_GLOBAL_VALUE_OPTS else 1
    if j >= len(argv):
        return None, []
    return argv[j], argv[j + 1 :]


def _short_ref(ref: str) -> str:
    ref = ref.lstrip("+")
    for prefix in ("refs/heads/", "refs/remotes/"):
        if ref.startswith(prefix):
            return ref[len(prefix) :]
    return ref


def _is_default_ref(ref: str, default_vars: set[str]) -> bool:
    """`main`, `origin/main`, `refs/heads/main`, or a variable that holds it."""
    parts = _short_ref(ref).split("/")
    name = parts[-1]
    if len(parts) <= 2 and name in _DEFAULT_BRANCHES:
        return True
    m = re.fullmatch(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)(?::?[-=]([^}]*))?\}?", name)
    return bool(m and (m.group(1) in default_vars or (m.group(2) or "") in _DEFAULT_BRANCHES))


def _default_vars(assigns: dict[str, list[str]], all_tokens: list[str]) -> set[str]:
    found: set[str] = set()
    for tok in all_tokens:
        for m in _PARAM_DEFAULT_RE.finditer(tok):
            if m.group(2) in _DEFAULT_BRANCHES:
                found.add(m.group(1))
    for _ in range(3):  # BASE=main; UPSTREAM=origin/$BASE
        for name, values in assigns.items():
            if any(_is_default_ref(v, found) for v in values):
                found.add(name)
    return found


def _names_a_source_branch(
    dst: str, assigns: dict[str, list[str]], bound: set[str], default_vars: set[str]
) -> bool:
    """A push destination that can be each proposed change's source branch.

    Fourteen branches cannot be one literal, so the destination has to expand a
    variable the script binds at run time: a loop or `read` variable, a function
    argument, or an assignment from a command. A placeholder (`<branch>`), an
    unbound `$var`, main, or a variable holding only a fixed literal does not.
    """
    if not dst or _is_default_ref(dst, default_vars) or dst.startswith("refs/tags/"):
        return False
    for name in (m.group(1) for m in _SHELL_VAR_RE.finditer(dst)):
        if name.isdigit() or name in {"@", "*"}:
            return True  # a function argument
        values = assigns.get(name, [])
        if values and any("$" in v or "`" in v for v in values):
            return True
        if name in bound and not values:
            return True
    return False


_BRACED_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*|[0-9@*])\}")


def _branch_ref(ref: str) -> str:
    """A ref as a branch name, with `${b}` and `$b` spelled the same way."""
    return _BRACED_VAR_RE.sub(r"$\1", _short_ref(ref))


def _function_name(tokens: list[str]) -> str | None:
    """The name a `name() {` or `function name {` line defines, if it is one."""
    if len(tokens) >= 2 and tokens[0] == "function":
        return tokens[1].removesuffix("()") or None
    if len(tokens) >= 2 and tokens[1] == "()" and re.fullmatch(r"[A-Za-z_][\w-]*", tokens[0]):
        return tokens[0]
    if len(tokens) >= 3 and tokens[1:3] == ["(", ")"] and re.fullmatch(r"[A-Za-z_][\w-]*", tokens[0]):
        return tokens[0]
    return None


def _function_bodies(lines: list[tuple[int, list[str]]]) -> dict[str, list[int]]:
    """Each function's name, with the positions in ``lines`` its body spans."""
    bodies: dict[str, list[int]] = {}
    current: str | None = None
    depth, opened = 0, False
    for pos, (_, tokens) in enumerate(lines):
        if current is None:
            current = _function_name(tokens)
            if current is None:
                continue
            bodies[current] = []
            depth, opened = 0, False
        bodies[current].append(pos)
        depth += tokens.count("{") - tokens.count("}")
        opened = opened or "{" in tokens
        if opened and depth <= 0:
            current = None
    return bodies


def _sent_graphql_lines(
    line_info: list[tuple[int, list[str], list[list[str]], set[str]]],
    assigns: dict[str, list[str]],
    bodies: list[tuple[int, str, int]],
    pattern: re.Pattern[str],
) -> list[int]:
    """Line indexes where ``pattern`` appears in text the script sends.

    Text counts on a line that runs a sender (curl, wget, httpie, infrahubctl,
    python, or a script function that calls one), in a variable such a line
    expands, and in a heredoc opened on such a line or assigned to such a
    variable. Text that is only echoed or printed is not a request.
    """
    funcs = _function_bodies([(idx, tokens) for idx, tokens, _, _ in line_info])

    def _program(argv: list[str]) -> str:
        return argv[0].rsplit("/", 1)[-1]

    sender_funcs: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, positions in funcs.items():
            if name in sender_funcs:
                continue
            for pos in positions:
                for argv in line_info[pos][2]:
                    prog = _program(argv)
                    if prog != name and (
                        prog in _SENDERS or prog.startswith("python") or prog in sender_funcs
                    ):
                        sender_funcs.add(name)
                        changed = True
                        break
                if name in sender_funcs:
                    break

    def _sends(argvs: list[list[str]]) -> bool:
        return any(
            (p := _program(a)) in _SENDERS or p.startswith("python") or p in sender_funcs
            for a in argvs
        )

    sender_pos = [pos for pos, (_, _, argvs, _) in enumerate(line_info) if _sends(argvs)]
    sent_vars = {
        m.group(1)
        for pos in sender_pos
        for tok in line_info[pos][1]
        for m in _SHELL_VAR_RE.finditer(tok)
    }

    found: list[int] = []
    for pos in sender_pos:
        idx, tokens, _, _ = line_info[pos]
        if pattern.search(" ".join(tokens)):
            found.append(idx)
    for idx, _, _, assigned in line_info:
        if any(pattern.search(v) for name in assigned & sent_vars for v in assigns[name]):
            found.append(idx)

    starts = [idx for idx, _, _, _ in line_info]
    sender_idx = {line_info[pos][0] for pos in sender_pos}
    for body_idx, body_line, opener in bodies:
        if not pattern.search(body_line):
            continue
        k = max((i for i, start in enumerate(starts) if start <= opener), default=None)
        if k is None:
            continue
        start, _, _, assigned = line_info[k]
        if start in sender_idx or assigned & sent_vars:
            found.append(body_idx)
    return found


def check_moves_source_branch_commit(
    config: dict, *, sh_raw: str = "", **_: Any
) -> tuple[bool, str]:
    """The script moves the repository commit each proposed change runs.

    Passes when a source branch has main merged, rebased or pulled into it and
    a later `git push` sends that branch to a source branch, or when the script
    opens a new branch and then a new proposed change. Rebasing the Infrahub
    branch and retrying the checks alone reruns the old commit on a branch
    synced with Git, and so does merging main into a branch other than the one
    pushed.
    """
    text = _shell_script_text(sh_raw or "")
    if not text.strip():
        return False, "output.sh is missing or empty"
    shell_lines, bodies = _split_heredocs(text)
    logical = _logical_lines(shell_lines)

    assigns: dict[str, list[str]] = {}
    bound: set[str] = set()
    commands: list[tuple[int, list[str]]] = []
    all_tokens: list[str] = []
    line_info: list[tuple[int, list[str], list[list[str]], set[str]]] = []
    for line_idx, tokens in logical:
        all_tokens.extend(tokens)
        line_assigns: dict[str, list[str]] = {}
        argvs: list[list[str]] = []
        for seg in _simple_commands(tokens):
            argv = _peel(seg, line_assigns)
            if argv:
                _bound_vars(argv, bound)
                commands.append((line_idx, argv))
                argvs.append(argv)
        for name, values in line_assigns.items():
            assigns.setdefault(name, []).extend(values)
        line_info.append((line_idx, tokens, argvs, set(line_assigns)))
    default_vars = _default_vars(assigns, all_tokens)

    current: str | None = None
    merged: set[str] = set()  # branches main was merged, rebased or pulled into
    qualifying_push: str | None = None
    pushes_seen: list[str] = []
    rebases = 0
    branch_create_lines: list[int] = []

    def _merged_into(target: str | None) -> None:
        if target and not _is_default_ref(target, default_vars):
            merged.add(target)

    for line_idx, argv in commands:
        if argv[0].rsplit("/", 1)[-1] == "infrahubctl" and argv[1:2] == [_BRANCH_GROUP]:
            verb = argv[2] if len(argv) > 2 else ""
            if verb == _BRANCH_CREATE:
                branch_create_lines.append(line_idx)
            elif verb == _BRANCH_REBASE:
                rebases += 1
        sub, args = _git_subcommand(argv)
        if sub is None:
            continue
        opts = _GIT_VALUE_OPTS.get(sub, set())
        pos = _positionals(args, opts)
        if sub in {"checkout", "switch"}:
            named = _option_value(args, {"-b", "-B", "-c", "-C"})
            if named:
                current = _branch_ref(named)
            elif pos:
                ref = pos[-1]
                if ("-t" in args or "--track" in args) and "/" in ref:
                    ref = ref.split("/", 1)[1]
                current = _branch_ref(ref)
        elif sub == "clone":
            named = _option_value(args, {"-b", "--branch"})
            current = _branch_ref(named) if named else None
        elif sub == "worktree" and pos[:1] == ["add"]:
            named = _option_value(args, {"-b", "-B"})
            ref = named or (pos[2] if len(pos) > 2 else None)
            current = _branch_ref(ref) if ref else current
        elif sub in {"merge", "rebase"}:
            refs = list(pos)
            if sub == "rebase" and len(pos) >= 2:
                # `git rebase <upstream> <branch>` checks out <branch> first.
                current = _branch_ref(pos[1])
                refs = [pos[0]]
            onto = _option_value(args, {"--onto"})
            if onto:
                refs.append(onto)
            if any(_is_default_ref(r, default_vars) for r in refs):
                _merged_into(current)
        elif sub == "pull":
            if any(_is_default_ref(r, default_vars) for r in pos[1:]):
                _merged_into(current)
        elif sub == "push":
            if {"--delete", "-d", "--all", "--mirror", "--tags"} & set(args):
                continue
            refspecs = pos[1:] or ["HEAD"]
            for spec in refspecs:
                if spec.startswith(":"):
                    continue
                src, dst = spec.split(":", 1) if ":" in spec else (spec, spec)
                src, dst = _branch_ref(src), _branch_ref(dst)
                if src == "HEAD":
                    src = current or ""
                if dst == "HEAD":
                    dst = current or ""
                pushes_seen.append(dst or "HEAD (branch unknown)")
                if (
                    qualifying_push is None
                    and src in merged
                    and _names_a_source_branch(dst, assigns, bound, default_vars)
                ):
                    qualifying_push = dst

    if qualifying_push:
        return True, (
            f"Pushes main into each source branch's Git branch (`git push` to {qualifying_push}), "
            "so the repository sync records a new commit on the branch"
        )

    # Second accepted route: a new branch, then a new proposed change on it.
    gql_branch = _sent_graphql_lines(line_info, assigns, bodies, _BRANCH_CREATE_GQL_RE)
    pc_create = _sent_graphql_lines(line_info, assigns, bodies, _PC_CREATE_GQL_RE)
    first_branch = min(branch_create_lines + gql_branch, default=None)
    if first_branch is not None and any(i >= first_branch for i in pc_create):
        return True, "Opens a new branch and a new proposed change, which run the current commit"

    seen = ", ".join(pushes_seen) if pushes_seen else "none"
    into = ", ".join(sorted(merged)) if merged else "none"
    return False, (
        "No `git push` to a source branch after merging or rebasing main into it, and no new "
        "branch plus new proposed change: the open proposed changes keep running the old "
        f"repository commit (git push destinations: {seen}; infrahubctl branch rebase calls: "
        f"{rebases}; branches main was merged into: {into})"
    )


# ---------------------------------------------------------------------------
# Check registry
# ---------------------------------------------------------------------------

CHECKS: dict[str, Any] = {
    "uses-sdk-execute-graphql": check_uses_sdk_execute_graphql,
    "no-status-code-branch": check_no_status_code_branch,
    "catches-graphql-error": check_catches_graphql_error,
    "separate-local-bounds-branch": check_separate_local_bounds_branch,
    "shared-module-absolute-import": check_shared_module_absolute_import,
    "dockerfile-targets-base-venv": check_dockerfile_targets_base_venv,
    "dockerfile-uv-sync-inexact": check_dockerfile_uv_sync_inexact,
    "watch-declares-shared-package": check_watch_declares_shared_package,
    "check-definitions-present": check_check_definitions_present,
    "no-query-field-in-check-def": check_no_query_field_in_check_def,
    "only-allowed-fields-in-check-def": check_only_allowed_fields_in_check_def,
    "queries-section-present": check_queries_section_present,
    "check-def-required-fields": check_check_def_required_fields,
    "targeted-has-targets-and-parameters": check_targeted_has_targets_and_parameters,
    "moves-source-branch-commit": check_moves_source_branch_commit,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point
# ---------------------------------------------------------------------------


def run_checks(
    check_names: list[str],
    output_path: Path,
    py_path: Path | None = None,
    dockerfile_path: Path | None = None,
    sh_path: Path | None = None,
) -> dict:
    """Run named checks against an .infrahub.yml output and return skillgrade JSON.

    ``py_path``, ``dockerfile_path`` and ``sh_path`` are optional: error-surface
    checks inspect a Python check file, received as ``tree`` / ``py_raw``,
    shared-module checks also inspect a Dockerfile, received as
    ``dockerfile_raw``, and the proposed-change commit check inspects a shell
    script, received as ``sh_raw``.
    """
    config, _ = load_output(output_path)
    tree, py_raw = load_output_py(py_path) if py_path else (None, "")
    dockerfile_raw = ""
    if dockerfile_path:
        try:
            dockerfile_raw = Path(dockerfile_path).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            dockerfile_raw = ""
    sh_raw = ""
    if sh_path:
        try:
            sh_raw = Path(sh_path).read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            sh_raw = ""

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = CHECKS[name]
        try:
            ok, msg = fn(
                config,
                tree=tree,
                py_raw=py_raw,
                dockerfile_raw=dockerfile_raw,
                sh_raw=sh_raw,
            )
        except Exception as exc:  # pragma: no cover
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


# ---------------------------------------------------------------------------
# Text-based checks
# ---------------------------------------------------------------------------
#
# Some rules grade the produced artifacts (a `.gql` query and a Python check
# class), not the `.infrahub.yml` registration. Those checks take the raw
# file text rather than a parsed config, so they live in TEXT_CHECKS and run
# through run_text_checks. Each has the same (bool, str) contract as the
# config checks above.


def _traversed_node_blocks(gql: str) -> list[str]:
    """Selection set of every `node {` after the first (the filtered child's own).

    Excluding the first `node {` keeps the child's own `name { value }` from
    satisfying the fetch assertion, while returning *every* traversed block
    (not only the textually last one) so a correct answer whose comparison
    traversal is followed by a sibling selection still counts.
    """
    matches = list(re.finditer(r"node\s*{", gql))
    blocks: list[str] = []
    for m in matches[1:]:
        start = m.end() - 1  # index of the opening brace
        depth = 0
        for i in range(start, len(gql)):
            ch = gql[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(gql[start + 1 : i])
                    break
        else:
            blocks.append(gql[start + 1 :])  # unbalanced; grade against the remainder
    return blocks


def _skips_unresolvable_without_log(py: str) -> bool | None:
    """Does any `if` branch skip (continue/return) without logging first?

    Semantic, idiom-agnostic detection of the anti-pattern the rule forbids
    (`if dev is None: continue`), instead of matching guard syntax. Returns
    None when the source cannot be parsed, so the caller can fall back.
    """
    try:
        tree = ast.parse(textwrap.dedent(py))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        skips = any(isinstance(s, (ast.Continue, ast.Return)) for s in ast.walk(node))
        logged = any(
            isinstance(c, ast.Call)
            and isinstance(c.func, ast.Attribute)
            and c.func.attr == "log_error"
            for c in ast.walk(node)
        )
        if skips and not logged:
            return True
    return False


def text_child_status_filter(gql: str, py: str) -> tuple[bool, str]:
    """The query filters the child set by an attribute value (e.g. status__value:)."""
    if re.search(r"\w+__value\s*:", gql):
        return True, "Query filters children by an attribute value"
    return False, "Query has no `<attr>__value:` filter selecting the constrained children"


def text_traverses_related_node(gql: str, py: str) -> tuple[bool, str]:
    """The query nests into a related node (>= 2 `node {` blocks)."""
    opens = len(re.findall(r"node\s*{", gql))
    if opens >= 2:
        return True, f"Query traverses into a related node ({opens} `node {{` blocks)"
    return False, "Query does not traverse a relationship into a nested `node {` block"


def text_fetches_related_attribute_value(
    gql: str, py: str, attr: str = "status"
) -> tuple[bool, str]:
    """The *named* comparison attribute is selected inside a traversed related node.

    The assertion carries the rule's thesis — the comparison attribute has to
    be pulled in the same query — so it matches the attribute by name (default
    `status`). Fetching some other attribute (e.g. the parent's `name`) on the
    traversed node no longer passes, and the child's own attributes are
    excluded because the child's `node {` is skipped.
    """
    blocks = _traversed_node_blocks(gql)
    if not blocks:
        return False, "Query does not traverse into a related node"
    pattern = re.compile(rf"\b{re.escape(attr)}\s*\{{\s*value\b")
    if any(pattern.search(b) for b in blocks):
        return True, f"A traversed related node selects `{attr} {{ value }}` (parent state is fetched)"
    return False, f"No traversed related node selects `{attr} {{ value }}`; the comparison attribute is not fetched"


def text_uses_infrahubcheck(gql: str, py: str) -> tuple[bool, str]:
    """Python defines an InfrahubCheck subclass bound to a query."""
    if "InfrahubCheck" in py and re.search(r"query\s*=", py):
        return True, "Defines an InfrahubCheck with a `query =` binding"
    return False, "No InfrahubCheck subclass with a `query =` attribute"


def text_surfaces_violation(gql: str, py: str) -> tuple[bool, str]:
    """validate() surfaces a mismatch via log_error (blocks the merge)."""
    if re.search(r"log_error\s*\(", py):
        return True, "Reports a violation with log_error"
    return False, "validate() never calls log_error, so no violation is surfaced"


def text_null_safe_traversal(gql: str, py: str) -> tuple[bool, str]:
    """The relationship walk uses a null-guard idiom (`or {}` / `.get(k, {})`).

    Checks the idiom is present, not that every hop is covered (that would need
    to count hops against guards); the message says what it verifies.
    """
    if "or {}" in py or re.search(r"\.get\([^)]*,\s*{}\)", py):
        return True, "Relationship walk uses a null guard (`or {}` / `.get(k, {})`)"
    return False, "No null guard (`or {}` / `.get(k, {})`) on the relationship walk"


def text_flags_unresolvable_parent(gql: str, py: str) -> tuple[bool, str]:
    """An unresolvable related node is flagged, not silently skipped.

    Guards finding 2 semantically: any `if` branch that skips (continue/return)
    without a log_error is the anti-pattern (`if dev is None: continue`),
    regardless of how the condition is written. Passing also requires a
    log_error somewhere, so the unresolvable case is actually surfaced.
    """
    skips = _skips_unresolvable_without_log(py)
    if skips is None:  # unparseable — fall back to the classic textual anti-pattern
        classic = re.search(r"(is\s+None|if\s+not\s+[\w.\[\]()]+)\s*:\s*\n\s*(continue|return)\b", py)
        skips = bool(classic)
    if skips:
        return False, "An unresolvable-relationship branch skips (continue/return) without log_error"
    if not re.search(r"log_error\s*\(", py):
        return False, "No log_error on the unresolvable-relationship path"
    return True, "Flags an unresolvable related node instead of skipping it"


# Text checks take `(gql, py)` positionally. The error-surface and
# shared-module checks take keyword-only sources and belong in CHECKS, which
# `run_checks` drives. They are deliberately absent here.
TEXT_CHECKS: dict[str, Any] = {
    "child-status-filter": text_child_status_filter,
    "traverses-related-node": text_traverses_related_node,
    "fetches-related-attribute-value": text_fetches_related_attribute_value,
    "uses-infrahubcheck": text_uses_infrahubcheck,
    "surfaces-violation": text_surfaces_violation,
    "null-safe-traversal": text_null_safe_traversal,
    "flags-unresolvable-parent": text_flags_unresolvable_parent,
}


def run_text_checks(
    check_names: list[str], sources: dict[str, str], attr: str = "status"
) -> dict:
    """Run named TEXT_CHECKS against produced source files and return skillgrade JSON.

    `sources` maps a label (e.g. "gql", "py") to that file's raw text. `attr` is
    the comparison attribute the query must fetch on the related node, passed to
    the fetch check so it stays generic per task rather than hardcoded.
    """
    gql = sources.get("gql", "")
    py = sources.get("py", "")

    entries: list[dict] = []
    passed_count = 0
    for name in check_names:
        fn = TEXT_CHECKS[name]
        try:
            if name == "fetches-related-attribute-value":
                ok, msg = fn(gql, py, attr)
            else:
                ok, msg = fn(gql, py)
        except Exception as exc:  # pragma: no cover
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
