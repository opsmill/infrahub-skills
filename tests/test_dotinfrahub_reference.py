"""The `.infrahub.yml` reference must enumerate every section the SDK defines.

`skills/infrahub-common/infrahub-yml-reference.md` heads its YAML block
"Complete Structure" and carries a `### \\`section\\`` subsection per key. An
agent reads that as the list of what `.infrahub.yml` supports, so a section
missing from it is not a gap the reader notices — it reads as a feature that
does not exist, and the agent reports the capability as unavailable.

`graphql_fragments` was absent for exactly that reason. The fix is one
section; this test is what stops the next one going the same way, because
Infrahub adds keys to `InfrahubRepositoryConfig` and nothing here tracks it.

Both directions are asserted: a pinned section missing from the reference,
and a documented section the SDK does not define (a rename or an invention).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "infrahub-common"
    / "infrahub-yml-reference.md"
)

# The top-level fields of `InfrahubRepositoryConfig`, read from
# infrahub-sdk-python at tag v1.23.2 (32cb8aa446ad9c8290304e488403be79ab6320d2):
#
#   git -C <sdk> show v1.23.2:infrahub_sdk/schema/repository.py \
#     | awk '/^class InfrahubRepositoryConfig\(BaseModel\)/,/@field_validator/' \
#     | grep -oE "^    [a-z0-9_]+:" | tr -d ' :'
#
# Pinned rather than imported: this repository ships no Python runtime
# dependency on infrahub-sdk, and `graders/common/cli_tree.py` already
# establishes the pattern of pinning an SDK surface with the version it was
# read at. Re-run the command above when bumping the pin.
SDK_VERSION = "1.23.2"
SECTIONS = (
    "check_definitions",
    "schemas",
    "jinja2_transforms",
    "artifact_definitions",
    "python_transforms",
    "generator_definitions",
    "queries",
    "graphql_fragments",
    "objects",
    "menus",
)

_STRUCTURE_HEADING = re.compile(r"^##\s+Complete Structure\s*$", re.MULTILINE)
_NEXT_H2 = re.compile(r"^##\s+", re.MULTILINE)
# `### \`queries\`` — the per-section heading. Backticked, so prose naming a
# section in passing is not mistaken for documenting it.
_SECTION_HEADING = re.compile(r"^###\s+`([a-z0-9_]+)`\s*$", re.MULTILINE)


def structure_block(text: str) -> str:
    """The body under `## Complete Structure`, up to the next `##`."""
    start = _STRUCTURE_HEADING.search(text)
    if start is None:
        return ""
    rest = text[start.end() :]
    end = _NEXT_H2.search(rest)
    return rest[: end.start()] if end else rest


def structure_keys(text: str) -> set[str]:
    """Top-level YAML keys declared in the Complete Structure block.

    Read line-wise rather than with a YAML parser: the block is illustrative
    and carries `...` elisions and comments that make it invalid YAML.
    """
    return {
        m.group(1)
        for m in re.finditer(r"^([a-z0-9_]+):", structure_block(text), re.MULTILINE)
    }


def documented_sections(text: str) -> set[str]:
    """Sections carrying their own `### \\`name\\`` subsection."""
    return {m.group(1) for m in _SECTION_HEADING.finditer(text)}


@pytest.fixture(scope="module")
def reference_text() -> str:
    return REFERENCE.read_text(encoding="utf-8")


@pytest.mark.parametrize("section", SECTIONS)
def test_section_in_structure_block(reference_text: str, section: str) -> None:
    """Every SDK section appears in the block headed "Complete Structure"."""
    assert section in structure_keys(reference_text), (
        f"`{section}` is a top-level key of InfrahubRepositoryConfig "
        f"(infrahub-sdk {SDK_VERSION}) but is missing from the Complete "
        f"Structure block of {REFERENCE.name}"
    )


@pytest.mark.parametrize("section", SECTIONS)
def test_section_has_subsection(reference_text: str, section: str) -> None:
    """Every SDK section has its own `### \\`name\\`` subsection."""
    assert section in documented_sections(reference_text), (
        f"`{section}` has no `### \\`{section}\\`` subsection in "
        f"{REFERENCE.name}; a section named only in passing is not documented"
    )


def test_no_section_the_sdk_does_not_define(reference_text: str) -> None:
    """The reference documents nothing InfrahubRepositoryConfig lacks.

    The other direction: catches a section renamed upstream, or one invented
    here, which would send a reader to write a key the config model forbids
    (`extra="forbid"`, so it fails the import rather than being ignored).
    """
    unknown = documented_sections(reference_text) - set(SECTIONS)
    assert not unknown, (
        f"{REFERENCE.name} documents section(s) {sorted(unknown)} that are not "
        f"fields of InfrahubRepositoryConfig at infrahub-sdk {SDK_VERSION}"
    )


# ---------------------------------------------------------------------------
# The parsers, verified both ways against hand-written references.
#
# The near miss is the case that matters: a reference naming the section in
# prose while the structure block and the subsections still omit it. It
# satisfies any check that greps the file for the word, and leaves the
# enumeration exactly as incomplete as before.
# ---------------------------------------------------------------------------

_COMPLETE = """# .infrahub.yml Configuration Reference

## Complete Structure

```yaml
# GraphQL queries
queries:
  - name: q
    file_path: "queries/q.gql"

# Fragments
graphql_fragments:
  - name: f
    file_path: "fragments/f.gql"
```

## Section Details

### `queries`

Text.

### `graphql_fragments`

Text.
"""

# Same substance, different surface: sections in the other order, a prose
# paragraph between them, and an extra `##` section after the details.
_COMPLETE_VARIANT = """# .infrahub.yml Configuration Reference

## Complete Structure

```yaml
graphql_fragments:
  - file_path: "fragments/"
    name: f

queries:
  - name: q
    file_path: "queries/q.gql"
```

## Section Details

### `graphql_fragments`

Declares reusable fragment files.

### `queries`

Registers query files.

## Loading Order

Schemas first.
"""

_MISSING = """# .infrahub.yml Configuration Reference

## Complete Structure

```yaml
queries:
  - name: q
    file_path: "queries/q.gql"
```

## Section Details

### `queries`

Text.
"""

_NEAR_MISS = """# .infrahub.yml Configuration Reference

## Complete Structure

```yaml
queries:
  - name: q
    file_path: "queries/q.gql"
```

## Section Details

### `queries`

Registers query files. Related settings such as `graphql_fragments` are
covered in the Infrahub documentation.
"""


@pytest.mark.parametrize(
    ("label", "text", "expected"),
    [
        ("complete", _COMPLETE, True),
        ("complete-variant", _COMPLETE_VARIANT, True),
        ("missing", _MISSING, False),
        ("near-miss", _NEAR_MISS, False),
    ],
)
def test_parsers_detect_a_missing_section(label: str, text: str, expected: bool) -> None:
    documented = (
        "graphql_fragments" in structure_keys(text)
        and "graphql_fragments" in documented_sections(text)
    )
    assert documented is expected, f"fixture {label!r} graded wrong"
