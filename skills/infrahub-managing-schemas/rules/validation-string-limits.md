---
title: Schema String-Length Limits
impact: HIGH
tags: validation, description, label, identifier, max_length, schema-load
---

## Schema String-Length Limits

Impact: HIGH

Several string fields on schema nodes, attributes, and
relationships have hard `max_length` caps enforced by
Pydantic on the server. Violations are not caught by
YAML editors or by `infrahubctl schema check` — they
fire at `infrahubctl schema load` time as

```text
Unable to load the schema:
    Node: <Kind> | <Field>: <name>
    | Input should have at most 128 characters (string_too_long)
```

…which means a schema that "looked fine" all the way
through review and CI rejects on the apply step. Treat
`description:` as a one-line tooltip, not a place to
document picker behavior, validation rules, or change
history.

### Verified limits

Source: Infrahub `1.9.4`, generated Pydantic models.

| Where | Field | Max | Min | Pattern |
| ----- | ----- | --- | --- | ------- |
| Node / Generic | `name` | 32 | 2 | `^[A-Z][a-zA-Z0-9]+$` |
| Node / Generic | `namespace` | 64 | 3 | `^[A-Z][a-z0-9]+$` |
| Node / Generic | `description` | **128** | — | — |
| Node / Generic | `label` | 64 | — | — |
| Attribute | `name` | 64 | 3 | `^[a-z0-9_]+$` |
| Attribute | `label` | 64 | — | — |
| Attribute | `description` | **128** | — | — |
| Attribute | `deprecation` | 128 | — | — |
| Relationship | `name` | 64 | 3 | `^[a-z0-9_]+$` |
| Relationship | `label` | 64 | — | — |
| Relationship | `description` | **128** | — | — |
| Relationship | `identifier` | 128 | — | `^[a-z0-9_]+$` |
| Relationship | `deprecation` | 128 | — | — |

Dropdown `choices[].description` has no length cap
in 1.9.4 (`backend/infrahub/core/schema/dropdown.py`
line 12 — `description: str | None = None`, no
Pydantic `Field(...)` wrapper). The choice `name` is
also unbounded at the model layer, but you'll hit
UI / GraphQL friction long before any practical
length.

### Incorrect

A long, helpful-looking description that paste
straight from a design doc — 364 characters:

```yaml
relationships:
  - name: cpe_handover_interface
    peer: DcimInterface
    kind: Attribute
    description: >-
      Port on a CSW (customer switch) where the provider's
      backbone hands traffic off to the customer's CPE. The
      picker walks SbsDevice → SbsPhysicalInterface via the
      peer's HFID; pick a CSW device (e.g. csw01.sjc2) and then
      its handover port. Non-CSW devices are rejected at submit
      by the generator's `_validate()` step.
```

At schema-load time:

```text
$ infrahubctl schema load schemas/
Unable to load the schema:
    Node: SbsL3VPNIntent | Relationship: cpe_handover_interface
    Port on a CSW (customer switch) where the provider's backbone hands traffic off to the customer's CPE. ...
    | Input should have at most 128 characters (string_too_long)
```

`infrahubctl schema check` (offline JSON Schema lint)
does **not** flag this — the JSON Schema generation
drops `max_length` constraints in some paths, so only
the live server enforces it. CI that only runs
`schema check` will miss it.

### Correct

Short, tooltip-sized `description:`. Put the
operator-facing detail in a YAML comment so it lives
in the file but doesn't fight the limit:

```yaml
relationships:
  # Picker walks SbsDevice → SbsPhysicalInterface via the
  # peer's HFID. The generator's _validate() step rejects
  # non-CSW devices at submit, so this relationship only
  # constrains the picker's *shape*, not its acceptance.
  - name: cpe_handover_interface
    peer: DcimInterface
    kind: Attribute
    description: CSW port where provider hands off to the customer CPE.
```

`description` is what shows up in the UI tooltip and
the GraphQL introspection — it should be one sentence
a user can read at a glance. Anything longer belongs
in surrounding YAML/Python comments, in
`documentation:` (a free-text URL field with no
length cap, line 96-99 of `base_node_schema.py`), or
in the project's design docs.

### Pre-flight check

`infrahubctl schema load` is too late — by then
you've already pushed the branch. Drop this into
project CI or a pre-commit hook to catch the
violation locally:

```python
# scripts/check_schema_string_limits.py
import sys
from pathlib import Path

import yaml

LIMITS = {
    "name": {"node": 32, "attr_rel": 64},
    "namespace": 64,
    "label": 64,
    "description": 128,
    "identifier": 128,
    "deprecation": 128,
}


def check_field(path: str, key: str, value: str, limit: int) -> str | None:
    if isinstance(value, str) and len(value) > limit:
        return f"{path}.{key}: {len(value)} chars (max {limit})"
    return None


def walk(doc: dict, file_path: str) -> list[str]:
    issues: list[str] = []
    for kind in ("nodes", "generics"):
        for node in doc.get(kind, []) or []:
            ref = f"{file_path}:{node.get('namespace', '?')}{node.get('name', '?')}"
            for k in ("namespace", "label", "description"):
                if msg := check_field(ref, k, node.get(k), LIMITS[k]):
                    issues.append(msg)
            if msg := check_field(ref, "name", node.get("name", ""), LIMITS["name"]["node"]):
                issues.append(msg)
            for attr in node.get("attributes", []) or []:
                aref = f"{ref}.{attr.get('name', '?')}"
                for k in ("label", "description", "deprecation"):
                    if msg := check_field(aref, k, attr.get(k), LIMITS[k]):
                        issues.append(msg)
                if msg := check_field(aref, "name", attr.get("name", ""), LIMITS["name"]["attr_rel"]):
                    issues.append(msg)
            for rel in node.get("relationships", []) or []:
                rref = f"{ref}.{rel.get('name', '?')}"
                for k in ("label", "description", "identifier", "deprecation"):
                    if msg := check_field(rref, k, rel.get(k), LIMITS[k]):
                        issues.append(msg)
                if msg := check_field(rref, "name", rel.get("name", ""), LIMITS["name"]["attr_rel"]):
                    issues.append(msg)
    return issues


issues: list[str] = []
for path in sys.argv[1:]:
    doc = yaml.safe_load(Path(path).read_text()) or {}
    issues.extend(walk(doc, path))

for line in issues:
    print(line)
sys.exit(1 if issues else 0)
```

Run as `python scripts/check_schema_string_limits.py
schemas/*.yml`. The Python walker handles YAML
folding (`>-`, `>`) correctly — a grep-based
one-liner does not.

### Why this isn't enforced earlier

The schema-load validator is the Pydantic models
generated under
`backend/infrahub/core/schema/generated/`. The
client-side JSON Schema export
(`https://schema.infrahub.app/infrahub/schema/latest.json`,
referenced by the `# yaml-language-server` comment)
covers naming patterns and required fields but
omits the `max_length` constraints on `description`,
`label`, `identifier`, and `deprecation`. Editor
warnings, `infrahubctl schema check`, and most CI
linters all use the JSON Schema and therefore
silently pass over-limit values. Only the server's
Pydantic models in production enforce the cap. That
gap is the reason this rule exists.

### Source

Verified against `infrahub-v1.9.4` (latest at the
time of writing). All limits come from generated
Pydantic `Field(...)` declarations:

- Node / Generic `name`, `namespace`, `description`,
  `label`:
  [backend/infrahub/core/schema/generated/base_node_schema.py](https://github.com/opsmill/infrahub/blob/infrahub-v1.9.4/backend/infrahub/core/schema/generated/base_node_schema.py)
  lines 17-44
- Attribute `name`, `label`, `description`,
  `deprecation`:
  [backend/infrahub/core/schema/generated/attribute_schema.py](https://github.com/opsmill/infrahub/blob/infrahub-v1.9.4/backend/infrahub/core/schema/generated/attribute_schema.py)
  lines 26-32, 67-77, 133-137
- Relationship `name`, `label`, `description`,
  `identifier`, `deprecation`:
  [backend/infrahub/core/schema/generated/relationship_schema.py](https://github.com/opsmill/infrahub/blob/infrahub-v1.9.4/backend/infrahub/core/schema/generated/relationship_schema.py)
  lines 23-29, 42-52, 54-59, 136-140
- Dropdown `choices[].description` (no limit):
  [backend/infrahub/core/schema/dropdown.py](https://github.com/opsmill/infrahub/blob/infrahub-v1.9.4/backend/infrahub/core/schema/dropdown.py)
  line 12
