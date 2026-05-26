---
title: Common Validation Errors and Fixes
impact: LOW
tags: validation, errors, debugging, additionalProperties
---

## Common Validation Errors and Fixes

Impact: LOW (but saves debugging time)

A lookup table that maps the validator's error
messages to the rule files that explain how to fix
them.

> **Note on `MUST`/`must` in this file and in
> [relationship-defaults.md](./relationship-defaults.md)
> and
> [relationship-component-parent.md](./relationship-component-parent.md):**
> any `must` appearing inside a quoted string or
> backticks is a verbatim Infrahub server error
> message — kept literal so users can grep their
> actual error output against the docs. Do not
> rewrite those occurrences.

### Why it matters

The Infrahub JSON schema is `additionalProperties:
false` — every typo in a property name surfaces as a
generic "unknown field" instead of a hint at the
correct spelling. The error messages from
`_validate_parents_one_schema` and the relationship
validator are similarly terse: they name the
violated rule but not the file or the fix. This
table closes that gap, pointing each error message
at the rule file that explains what to change and
why the validator rejects the current shape.

### "Unknown field"

A typo in a property name:

```yaml
# BAD - typo
- name: MyNode
  namspace: Dcim         # Should be "namespace"
```

### "Name must match pattern"

Naming convention violation. See the
[naming-conventions](./naming-conventions.md) rule.

### "Peer not found"

Missing namespace in peer reference. See the
[relationship-peer-kind](./relationship-peer-kind.md) rule.

### "Identifier mismatch"

Bidirectional relationship identifiers don't match. See the
[relationship-identifiers](./relationship-identifiers.md) rule.

### "Relationship of type parent must not be optional"

A relationship with `kind: Parent` has `optional: true`
(or no explicit value — relationships default to
optional). Set `optional: false` on the Parent side.
See [relationship-component-parent](./relationship-component-parent.md).

### "Relationship of type parent must be cardinality=one"

A `kind: Parent` relationship has `cardinality: many`
or no explicit cardinality (which defaults to
`many`). Set `cardinality: one`. See
[relationship-component-parent](./relationship-component-parent.md).

### "Only one relationship of type parent is allowed"

A node has more than one relationship with
`kind: Parent`. Pick the canonical owner; model the
others as `kind: Attribute` or `kind: Generic`
references. See
[relationship-component-parent](./relationship-component-parent.md).

### "Uniqueness constraint references unknown field"

Wrong format in constraints. See the
[uniqueness-constraints](./uniqueness-constraints.md) rule.

### "Unable to load the schema:" with empty body

When `infrahubctl schema load` prints
`Unable to load the schema:` followed by nothing,
the CLI couldn't parse the response far enough to
report which file failed. Bisect by directory and
then by file with `infrahubctl schema check`,
which gives a real error (line number, field
name) per-file. The empty-body symptom only
appears at `schema load`.

```bash
# Bisect by directory
for dir in schemas/*/; do
  echo "=== $dir ==="; infrahubctl schema check "$dir"
done
```

### "Input should have at most N characters (string_too_long)"

A schema-load-time Pydantic error on
`description` (128), `label` (64), `identifier`
(128), or `deprecation` (128). Not caught by
`infrahubctl schema check` — only by
`infrahubctl schema load`. See
[validation-string-limits](./validation-string-limits.md) for
the verified per-field caps and a Python preflight
walker.

### Pre-Validation Checklist

Before running `infrahubctl schema check`, verify:

- [ ] Every schema file starts with `version: "1.0"`
- [ ] All node/generic names are PascalCase
- [ ] All namespaces match `^[A-Z][a-z0-9]+$`
- [ ] All attribute/relationship names are snake_case, 3+ chars
- [ ] All `peer` values use full kind (namespace + name)
- [ ] All bidirectional relationships have matching `identifier`
- [ ] All Component relationships have a matching Parent
- [ ] Every `kind: Parent` relationship has
  `cardinality: one` and `optional: false`
- [ ] No node has more than one `kind: Parent`
  relationship
- [ ] All hierarchical nodes inherit from a `hierarchical: true` generic
- [ ] Root hierarchical nodes have `parent: null`
- [ ] All Dropdown attributes have `choices` defined
- [ ] `human_friendly_id` is set on user-facing nodes
- [ ] `uniqueness_constraints` use `__value` for attributes
- [ ] The `$schema` comment is present for IDE validation

```bash
# Validate
infrahubctl schema check schemas/

# Load
infrahubctl schema load schemas/ --branch main
```

Reference: [validation.md](../validation.md) for full validation and migration guide.
