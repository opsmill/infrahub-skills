"""The `.infrahub.yml` reference must enumerate every section the SDK defines.

`skills/infrahub-common/infrahub-yml-reference.md` heads its YAML block
"Complete Structure" and carries a `### \\`section\\`` subsection per key. An
agent reads that as the list of what `.infrahub.yml` supports, so a section
missing from it is not a gap the reader notices: it reads as a feature that
does not exist, and the agent reports the capability as unavailable.

`graphql_fragments` was absent for exactly that reason. The fix is one
section; this test is what stops the next one going the same way.

The section list is read from `InfrahubRepositoryConfig` rather than pinned,
so a field added upstream turns into a failure here the moment the SDK is
updated. A literal tuple could not do that: a new key would be absent from
both the pin and the reference, and every assertion would still pass while
the reference silently fell behind. `infrahub-sdk` is a declared dependency
of the `test` group, which is what makes reading the model possible.

Both directions are asserted: a section missing from the reference, and a
documented section the SDK does not define (a rename or an invention).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from infrahub_sdk.schema.repository import InfrahubRepositoryConfig

REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "infrahub-common"
    / "infrahub-yml-reference.md"
)

# The top-level fields of the model that parses `.infrahub.yml`.
SECTIONS = tuple(InfrahubRepositoryConfig.model_fields)

# `### \`queries\`` — the per-section heading. Backticked, so prose naming a
# section in passing is not mistaken for documenting it.
_SECTION_HEADING = re.compile(r"^###\s+`([a-z0-9_]+)`\s*$", re.MULTILINE)
_NEXT_H2 = re.compile(r"^##\s+", re.MULTILINE)


def h2_block(text: str, title: str) -> str:
    """The body under `## <title>`, up to the next `##`."""
    start = re.search(rf"^##\s+{re.escape(title)}\s*$", text, re.MULTILINE)
    if start is None:
        return ""
    rest = text[start.end() :]
    end = _NEXT_H2.search(rest)
    return rest[: end.start()] if end else rest


def structure_keys(text: str) -> set[str]:
    """Top-level YAML keys declared in the Complete Structure block.

    Read line-wise rather than with a YAML parser: the block is illustrative
    and carries comments and elisions that make it invalid YAML.
    """
    return {
        m.group(1)
        for m in re.finditer(
            r"^([a-z0-9_]+):", h2_block(text, "Complete Structure"), re.MULTILINE
        )
    }


def documented_sections(text: str) -> set[str]:
    """Sections carrying their own `### \\`name\\`` subsection.

    Scoped to the Section Details block rather than the whole file, so a
    backticked H3 elsewhere is not read as documenting a config key. The
    file already keeps sub-field pages (`## The watch Field`) at H2, and
    promoting one to H3 should not fail this test.
    """
    return {
        m.group(1) for m in _SECTION_HEADING.finditer(h2_block(text, "Section Details"))
    }


@pytest.fixture(scope="module")
def reference_text() -> str:
    return REFERENCE.read_text(encoding="utf-8")


@pytest.mark.parametrize("section", SECTIONS)
def test_section_in_structure_block(reference_text: str, section: str) -> None:
    """Every SDK section appears in the block headed "Complete Structure"."""
    assert section in structure_keys(reference_text), (
        f"`{section}` is a top-level field of InfrahubRepositoryConfig but is "
        f"missing from the Complete Structure block of {REFERENCE.name}"
    )


@pytest.mark.parametrize("section", SECTIONS)
def test_section_has_subsection(reference_text: str, section: str) -> None:
    """Every SDK section has its own `### \\`name\\`` subsection."""
    assert section in documented_sections(reference_text), (
        f"`{section}` has no `### \\`{section}\\`` subsection under Section "
        f"Details in {REFERENCE.name}; a section named only in passing is "
        f"not documented"
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
        f"fields of InfrahubRepositoryConfig"
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
queries:
  - name: q
    file_path: "queries/q.gql"

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

# Same substance, different surface: the other order, and a trailing `##`
# section, so the Section Details slice has to stop at the right place.
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
    documented = "graphql_fragments" in structure_keys(text) and (
        "graphql_fragments" in documented_sections(text)
    )
    assert documented is expected, f"fixture {label!r} graded wrong"


def test_h3_outside_section_details_is_not_a_config_key() -> None:
    """A backticked H3 in another `##` block is not read as a section.

    Sub-field documentation sits at H2 today. Promoting one to H3 is a
    formatting choice, not a claim that `watch` is a top-level key, and it
    must not fail `test_no_section_the_sdk_does_not_define`.
    """
    text = _COMPLETE + "\n## The watch Field\n\n### `watch`\n\nNot a top-level key.\n"
    assert documented_sections(text) == {"queries", "graphql_fragments"}
