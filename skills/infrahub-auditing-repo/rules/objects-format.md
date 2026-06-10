---
title: objects-format
impact: CRITICAL
tags: audit, objects
---

# Rule: objects-format

**Severity**: CRITICAL
**Category**: Objects

## What It Checks

Validates that object YAML files follow the
required `apiVersion` / `kind` / `spec` envelope
and the value conventions for `spec.kind`,
`spec.data`, multi-document separation, and
`expand_range` placement.

## Why it matters

Object loaders parse each YAML document through a
strict Pydantic model — a missing `apiVersion`,
the wrong `kind`, or `spec.data` shaped as a dict
instead of a list causes the entire file to fail
to load, and `infrahubctl object load` exits non-
zero before any object reaches the database. The
fix is mechanical once the violation is named, but
without this audit step the operator hits a wall
of validation tracebacks and has to bisect which
document triggered it. `expand_range` on the wrong
level is the silent variant — the load succeeds
but creates one literal item instead of expanding
the range.

## Checks

1. Each YAML document has `apiVersion: infrahub.app/v1`
2. Each document has `kind: Object`
3. `spec.kind` is present and uses full kind (Namespace + Name)
4. `spec.data` is present and is a list
5. One kind per YAML document (use `---` separator for multiple)
6. `expand_range: true` is in `parameters` block, not on individual items
7. Hierarchical children include `kind` field at each level
8. Component children include `kind` field under relationship name

## Common Issues

- Missing `apiVersion` field
- `spec.data` as an object instead of a list
- Multiple kinds in a single YAML document without `---` separator
- `expand_range` placed on data items instead of `parameters`
