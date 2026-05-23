"""Shared grader library for infrahub-managing-generators skill evaluations.

Generator output is multi-file: a Python class under ``generators/``, a GraphQL
query under ``queries/``, and a registration block in ``.infrahub.yml``. Each
check function receives a project root ``Path`` and inspects whichever files it
needs.

Usage (in a per-task grader script)::

    from pathlib import Path
    from lib import run_checks

    result = run_checks(
        ["allow-upsert-everywhere", "upstream-count-validation"],
        Path("."),
    )
    print(result)  # {"score": 1.0, "details": "...", "checks": [...]}
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError("PyYAML is required: pip install pyyaml") from exc


# ---------------------------------------------------------------------------
# File discovery and AST helpers
# ---------------------------------------------------------------------------


def find_generator_files(root: Path) -> list[Path]:
    """Find generator Python files in a project root.

    Looks under ``generators/`` first, then falls back to any top-level ``.py``
    file that imports ``InfrahubGenerator``.
    """
    candidates: list[Path] = []

    gen_dir = root / "generators"
    if gen_dir.is_dir():
        candidates.extend(p for p in gen_dir.glob("*.py") if p.name != "__init__.py")

    if not candidates:
        for p in root.glob("*.py"):
            try:
                if "InfrahubGenerator" in p.read_text(encoding="utf-8"):
                    candidates.append(p)
            except OSError:
                continue

    return candidates


def parse_python(path: Path) -> ast.Module | None:
    """Parse a Python file to an AST, returning None on read or syntax error."""
    try:
        src = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return ast.parse(src)
    except SyntaxError:
        return None


def generate_methods(tree: ast.AST) -> list[ast.AsyncFunctionDef]:
    """Return all ``async def generate(...)`` methods in the AST."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "generate"
    ]


def _calls_named(tree: ast.AST, attr_name: str) -> list[ast.Call]:
    """Return all ``foo.<attr_name>(...)`` calls in the AST."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attr_name
    ]


def save_calls(tree: ast.AST) -> list[ast.Call]:
    """Return all ``.save(...)`` method calls."""
    return _calls_named(tree, "save")


def create_calls(tree: ast.AST) -> list[ast.Call]:
    """Return all ``.create(...)`` method calls (matches ``self.client.create``)."""
    return _calls_named(tree, "create")


# ---------------------------------------------------------------------------
# Check functions — universal tier
# ---------------------------------------------------------------------------


def check_allow_upsert_everywhere(root: Path, **_: Any) -> tuple[bool, str]:
    """Every ``.save(...)`` call must include ``allow_upsert=True``.

    Without the flag, re-running the generator raises on existing nodes — the
    tracking system needs upserts for idempotent behavior.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found under generators/ or root"

    offenders: list[str] = []
    saw_any_save = False

    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"
        for call in save_calls(tree):
            saw_any_save = True
            has_upsert = any(
                kw.arg == "allow_upsert"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in call.keywords
            )
            if not has_upsert:
                offenders.append(f"{f.name}:{call.lineno}")

    if not saw_any_save:
        return False, "No .save() calls found in any generator file"
    if offenders:
        return (
            False,
            f".save() without allow_upsert=True at: {', '.join(offenders)}",
        )
    return True, "All .save() calls include allow_upsert=True"


def _stmt_contains_create(stmt: ast.AST) -> bool:
    """Does this statement (recursively) contain a ``.create(...)`` call?"""
    for node in ast.walk(stmt):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "create"
        ):
            return True
    return False


def _test_references_collection(test: ast.AST) -> bool:
    """Test references a count/collection: ``len(...)`` call or ``not <name>``.

    Accepts the three forms documented in validation-upstream-counts.md:
    ``len(elements) != expected``, ``assert len(elements) == expected``, and
    ``if not elements:``.
    """
    for sub in ast.walk(test):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "len"
        ):
            return True
        if isinstance(sub, ast.UnaryOp) and isinstance(sub.op, ast.Not):
            if isinstance(sub.operand, (ast.Name, ast.Attribute, ast.Subscript)):
                return True
    return False


def _body_aborts(body: list[ast.stmt]) -> bool:
    """Body's top-level statements include ``raise`` or ``return``."""
    for stmt in body:
        if isinstance(stmt, (ast.Raise, ast.Return)):
            return True
    return False


def check_upstream_count_validation(root: Path, **_: Any) -> tuple[bool, str]:
    """``generate()`` must abort on count mismatch before creating any object.

    Structural test (not just "len() appears somewhere"): walks the top-level
    statements of ``generate()`` in source order. Accepts a guard ONLY when:

    - An ``assert`` whose test references ``len(...)`` or ``not <name>``
      (asserts abort by themselves), OR
    - An ``if`` whose test references ``len(...)`` or ``not <name>`` AND
      whose body's top level contains ``raise`` or ``return``.

    Both must appear before the first top-level statement that contains
    a ``.create(...)`` call. A log-and-continue branch (e.g. ``if len(x): print(...)``)
    is correctly rejected because its body neither raises nor returns.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found"

    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"

        for gen_fn in generate_methods(tree):
            any_create = any(_stmt_contains_create(s) for s in gen_fn.body)
            if not any_create:
                continue  # generate() creates nothing — rule does not apply

            has_guard = False
            for stmt in gen_fn.body:
                if _stmt_contains_create(stmt):
                    break  # reached the create stmt; guard must have come earlier

                if isinstance(stmt, ast.Assert) and _test_references_collection(stmt.test):
                    has_guard = True
                    break
                if (
                    isinstance(stmt, ast.If)
                    and _test_references_collection(stmt.test)
                    and _body_aborts(stmt.body)
                ):
                    has_guard = True
                    break

            if not has_guard:
                return (
                    False,
                    f"{f.name}: generate() creates objects without a prior "
                    f"raising guard on len() or `not <collection>`",
                )

    return True, "Upstream count validation present before first .create()"


def check_stable_iteration(root: Path, **_: Any) -> tuple[bool, str]:
    """Create-loops must iterate ``sorted(...)``, ``range(...)``, or
    ``enumerate()`` of one of those.

    GraphQL response order is not guaranteed stable across runs. Iterating raw
    list responses inside a ``.create()`` loop lets ordering drift produce
    spurious name churn.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found"

    accepted_names = {"sorted", "range"}

    def _iter_is_deterministic(it: ast.AST) -> bool:
        # sorted(...) or range(...)
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name):
            if it.func.id in accepted_names:
                return True
            # enumerate(sorted(...)) or enumerate(range(...))
            if it.func.id == "enumerate" and it.args:
                inner = it.args[0]
                if (
                    isinstance(inner, ast.Call)
                    and isinstance(inner.func, ast.Name)
                    and inner.func.id in accepted_names
                ):
                    return True
        return False

    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"

        for gen_fn in generate_methods(tree):
            for node in ast.walk(gen_fn):
                if not isinstance(node, (ast.For, ast.AsyncFor)):
                    continue
                # Does this loop body contain a .create() call?
                if not any(
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "create"
                    for sub in ast.walk(node)
                ):
                    continue
                if not _iter_is_deterministic(node.iter):
                    return (
                        False,
                        f"{f.name}:{node.lineno}: create-loop iterates a "
                        f"non-deterministic collection (wrap in sorted() or "
                        f"iterate range())",
                    )

    return True, "All create-loops iterate sorted() or range()"


# ---------------------------------------------------------------------------
# Check functions — cascade tier (conditional, applies only when building
# modular cascading generators)
# ---------------------------------------------------------------------------


def _literal_kinds_in_generate(tree: ast.AST) -> set[str]:
    """Collect string-literal ``kind=...`` values from ``.create(...)`` calls
    inside ``generate()`` methods.

    Non-literal kinds (variables, attributes) are skipped — we can't statically
    tell what they resolve to.
    """
    kinds: set[str] = set()
    for gen_fn in generate_methods(tree):
        for call in create_calls(gen_fn):
            for kw in call.keywords:
                if (
                    kw.arg == "kind"
                    and isinstance(kw.value, ast.Constant)
                    and isinstance(kw.value.value, str)
                ):
                    kinds.add(kw.value.value)
    return kinds


def check_cascade_one_layer(root: Path, **_: Any) -> tuple[bool, str]:
    """Each generator file should create exactly one ``kind`` of object.

    A generator that creates two distinct kinds is doing two layers of work in
    one place, which breaks the modular-cascade boundary the docs prescribe.
    Multiple generator files in a project are fine — each owns its own layer.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found"

    offenders: list[str] = []
    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"
        kinds = _literal_kinds_in_generate(tree)
        if len(kinds) > 1:
            offenders.append(f"{f.name}: creates {sorted(kinds)}")

    if offenders:
        return (
            False,
            "Multi-layer generator(s) found: " + "; ".join(offenders),
        )
    return True, "Every generator file creates exactly one kind"


def _load_schemas(root: Path) -> list[dict]:
    """Load schema YAML(s) from the project root.

    Looks for ``schema.yml``, ``schema.yaml``, and ``schemas/*.yml``. Returns
    a list of parsed schema dicts (one per file).
    """
    docs: list[dict] = []
    candidates: list[Path] = []
    for name in ("schema.yml", "schema.yaml"):
        p = root / name
        if p.is_file():
            candidates.append(p)
    schemas_dir = root / "schemas"
    if schemas_dir.is_dir():
        candidates.extend(schemas_dir.glob("*.y*ml"))
    for p in candidates:
        try:
            parsed = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(parsed, dict):
            docs.append(parsed)
    return docs


def check_cascade_target_inheritance(root: Path, **_: Any) -> tuple[bool, str]:
    """At least one node in the schema inherits from a ``GeneratorTarget`` generic.

    Downstream nodes in a cascade must carry the ``checksum`` attribute that
    ``GeneratorTarget`` provides. Without it, the cascade has no way to skip
    re-triggering on unchanged inputs.

    Limitation: the check accepts ``GeneratorTarget`` on *any* node in the
    schema. It can't tell upstream design objects from downstream targets
    without semantic context. The eval task prompts therefore name the
    expected downstream kind explicitly (e.g., ``Device``) so a model that
    puts ``GeneratorTarget`` on the wrong node still fails task
    expectations even when this grader passes.
    """
    schemas = _load_schemas(root)
    if not schemas:
        return False, "No schema YAML found at root or under schemas/"

    for schema in schemas:
        nodes = (schema.get("nodes") or []) + (schema.get("generics") or [])
        for node in nodes:
            inherits = node.get("inherit_from") or []
            if isinstance(inherits, str):
                inherits = [inherits]
            for parent in inherits:
                if isinstance(parent, str) and "GeneratorTarget" in parent:
                    return (
                        True,
                        f"Node '{node.get('name', '?')}' inherits from {parent}",
                    )

    return False, "No node inherits from a GeneratorTarget generic"


def _test_mentions_checksum(test: ast.AST) -> bool:
    """Test references ``checksum`` via any common access pattern.

    Accepts attribute access (``device.checksum.value``), bare names
    (``new_checksum``), and dict-style subscripts (``device["checksum"]``)
    — all three appear in GraphQL response handling code.
    """
    for sub in ast.walk(test):
        if isinstance(sub, ast.Attribute) and "checksum" in sub.attr.lower():
            return True
        if isinstance(sub, ast.Name) and "checksum" in sub.id.lower():
            return True
        if (
            isinstance(sub, ast.Constant)
            and isinstance(sub.value, str)
            and "checksum" in sub.value.lower()
        ):
            return True
    return False


def _body_short_circuits(body: list[ast.stmt]) -> bool:
    """Body's top-level statements include ``continue``, ``return``, or ``break``."""
    for stmt in body:
        if isinstance(stmt, (ast.Continue, ast.Return, ast.Break)):
            return True
    return False


def _body_contains_save_or_create(body: list[ast.stmt]) -> bool:
    """Body (recursively) contains a ``.save(...)`` or ``.create(...)`` call."""
    for stmt in body:
        for sub in ast.walk(stmt):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr in ("save", "create")
            ):
                return True
    return False


def check_cascade_checksum_guard(root: Path, **_: Any) -> tuple[bool, str]:
    """The generator must contain a checksum-based guard that actually gates work.

    Accepts both documented forms:

    - **Skip-and-continue** — ``if existing.checksum.value == new_checksum: continue``
      (body short-circuits; create/save happens after the ``if``).
    - **Gate-the-create** — ``if existing.checksum.value != new_checksum: ... .save()``
      (body contains the create/save itself).

    A presence-only ``if`` whose body merely logs or prints is rejected — the
    cascade is not actually idempotent in that case.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found"

    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"
        for gen_fn in generate_methods(tree):
            for node in ast.walk(gen_fn):
                if not (isinstance(node, ast.If) and _test_mentions_checksum(node.test)):
                    continue
                if _body_short_circuits(node.body) or _body_contains_save_or_create(node.body):
                    return True, f"{f.name}: checksum guard at line {node.lineno}"

    return (
        False,
        "No checksum guard found whose body either short-circuits "
        "(continue/return/break) or contains a .save()/.create() call",
    )


def check_cascade_version_constant(root: Path, **_: Any) -> tuple[bool, str]:
    """Module defines a ``GENERATOR_VERSION`` constant.

    The constant is mixed into the checksum input so logic changes force a
    re-cascade even when input data is unchanged.
    """
    files = find_generator_files(root)
    if not files:
        return False, "No generator .py files found"

    for f in files:
        tree = parse_python(f)
        if tree is None:
            return False, f"Could not parse {f.name}"
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for target in targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "GENERATOR_VERSION"
                    ):
                        return True, f"{f.name}: GENERATOR_VERSION defined"

    return False, "No GENERATOR_VERSION module-level constant defined"


# ---------------------------------------------------------------------------
# CHECKS registry
# ---------------------------------------------------------------------------


CHECKS: dict[str, Any] = {
    "allow-upsert-everywhere": check_allow_upsert_everywhere,
    "upstream-count-validation": check_upstream_count_validation,
    "stable-iteration": check_stable_iteration,
    "cascade-one-layer": check_cascade_one_layer,
    "cascade-target-inheritance": check_cascade_target_inheritance,
    "cascade-checksum-guard": check_cascade_checksum_guard,
    "cascade-version-constant": check_cascade_version_constant,
}


# ---------------------------------------------------------------------------
# run_checks — top-level entry point for grader scripts
# ---------------------------------------------------------------------------


def run_checks(check_names: list[str], output_root: Path | None = None) -> dict:
    """Run named checks against a generator project root.

    Parameters
    ----------
    check_names:
        Names from the ``CHECKS`` registry.
    output_root:
        Project root where the model wrote ``generators/``, ``queries/``, and
        ``.infrahub.yml``. Defaults to the current directory.

    Returns
    -------
    dict with ``score`` (float), ``details`` (str), and ``checks`` (list of
    per-check entries) — the skillgrade JSON format.
    """
    root = output_root or Path(".")

    entries: list[dict] = []
    passed_count = 0

    for name in check_names:
        fn = CHECKS[name]  # raises KeyError for unknown names
        try:
            ok, msg = fn(root)
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
