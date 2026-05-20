---
title: Schema String-Length Limits
impact: HIGH
tags: validation, description, label, identifier, max_length, schema-load, string_too_long, openapi, json-schema, pre-flight
---

## Schema String-Length Limits

Impact: HIGH

### When this rule applies

Use this rule whenever you author or review a schema
field that takes free text — `description`, `label`,
`identifier`, `deprecation`, `name`, `namespace` — or
when triaging an `Input should have at most <N>
characters` failure from `infrahubctl schema load`.

The cap is enforced by Pydantic on the server. YAML
editors, `infrahubctl schema check`, and most CI
linters all silently let over-cap values through:

```text
Unable to load the schema:
    Node: <Kind> | <Field>: <name>
    | Input should have at most <N> characters (string_too_long)
```

A schema that "looked fine" through review and CI
will reject only on the apply step. Treat
`description:` as a one-line tooltip — picker behavior,
validation rules, and change history belong in
surrounding YAML comments or in `documentation:`.

### Source of truth

Caps drift between Infrahub versions; a static table
here would go stale silently. Resolve them at
validation time from one of two equivalent live
sources:

1. **Public JSON Schema** —
   `https://schema.infrahub.app/infrahub/schema/latest.json`.
   No auth, no running server. Same URL the
   `# yaml-language-server: $schema=...` IDE hint at
   the top of every schema file already points at.
2. **Running Infrahub** — `{BASE_URL}/api/openapi.json`.
   Identical constraint values, just a heavier path.

Property tables in [reference.md](../reference.md),
patterns in [naming-conventions.md](./naming-conventions.md),
and the guide in [validation.md](../validation.md)
deliberately carry only the stable regex patterns —
no length numbers — so the constraints live in
exactly one place: the live spec.

### Resolution procedure

Both tiers go through one cross-platform script,
[`scripts/fetch_schema_limits.py`](../scripts/fetch_schema_limits.py).
It uses only Python's stdlib so it runs identically
on macOS, Linux, and Windows. Output is ~1 KB of
JSON keyed by `NodeSchema`, `GenericSchema`,
`AttributeSchema`, `RelationshipSchema` — **read only
that into context, never the raw 66 KB schema or
100 KB OpenAPI document.**

```bash
# Tier 1 — public JSON Schema (default)
python skills/infrahub-managing-schemas/scripts/fetch_schema_limits.py
```

Exit 0 means the constraints are on stdout. Exit 1
means the source is unreachable — diagnostic on
stderr — fall through to Tier 2.

Tier 2 defers connectivity probing to
[connectivity-server-check.md](../../infrahub-common/rules/connectivity-server-check.md)
(it owns `INFRAHUB_ADDRESS`, `infrahubctl info`, and
the troubleshooting flow — do not duplicate any of it
here). Once it has established a reachable
`BASE_URL`:

```bash
# Tier 2 — running Infrahub /api/openapi.json (fallback)
python skills/infrahub-managing-schemas/scripts/fetch_schema_limits.py \
  --openapi "$BASE_URL"
```

The script normalises the OpenAPI naming difference
(`AttributeSchema-Input` → `AttributeSchema`), so the
output structure is identical regardless of source.

If both tiers fail, **do not fall back to hardcoded
numbers**. Warn the user that string-length
validation cannot be performed for this run and
continue with the rest of the review — regex
patterns can still be checked offline against
[naming-conventions.md](./naming-conventions.md).

### Field-to-key map

| Schema field | Lookup key in the script's output |
| ------------ | --------------------------------- |
| Node / Generic `name`, `namespace`, `label`, `description` | `NodeSchema.<field>` / `GenericSchema.<field>` |
| Attribute `name`, `label`, `description`, `deprecation` | `AttributeSchema.<field>` |
| Relationship `name`, `label`, `description`, `identifier`, `deprecation` | `RelationshipSchema.<field>` |

Each key carries `minLength`, `maxLength`, and/or
`pattern`. Emit over-cap errors as
`{kind}.{field}: <len> chars (max <cap>, from <source-url>)`
so the source is auditable — cite the URL, never a
version baked into prose.

### Incorrect — description used as a design doc

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

Editor and `schema check` pass. `schema load` rejects:

```text
$ infrahubctl schema load schemas/
Unable to load the schema:
    Node: SbsL3VPNIntent | Relationship: cpe_handover_interface
    Port on a CSW (customer switch) where the provider's backbone hands traffic off to the customer's CPE. ...
    | Input should have at most <N> characters (string_too_long)
```

### Correct — short description, detail in a comment

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

`description` surfaces in the UI tooltip and GraphQL
introspection — one sentence the operator reads at a
glance. Operator detail goes in surrounding comments
or in `documentation:` (a free-text URL field —
confirm its cap against the live spec if you fill
it).

### Pre-flight check (CI / pre-commit)

`infrahubctl schema load` is too late: the branch is
already pushed. The same script's `--check` mode
validates files locally against the live caps:

```bash
python skills/infrahub-managing-schemas/scripts/fetch_schema_limits.py \
  --check schemas/*.yml
```

Exit 0 if all files pass *or* if the live source is
unreachable (warning on stderr — skip-on-unreachable
keeps CI green during transient blips). Exit 1 if any
field is over its cap; each violation is printed as
`{path}:{Kind}.{field}: <len> chars (max <cap>)`.
Compose with `--openapi $BASE_URL` for the Tier 2
case.

### Common mistakes

| Mistake | Fix |
| ------- | --- |
| Hardcoding 128 / 64 / 32 in skill prose or AI output | Resolve at validation time from the live spec |
| Reading the raw 66 KB / 100 KB JSON into context | Always pipe through `fetch_schema_limits.py` — output is ~1 KB |
| Treating `description:` as a design-doc paragraph | One sentence; detail goes in YAML comments or `documentation:` |
| Falling back to baked-in numbers when both tiers fail | Warn and skip; over-cap fields will be caught at `schema load` |
| Inventing a `localhost:8000` fallback inside this rule | Tier 2 owns connectivity via `connectivity-server-check.md` |
