---
title: schema-naming
impact: CRITICAL
tags: audit, schema, naming
---

# Rule: schema-naming

**Severity**: CRITICAL
**Category**: Schema

## What It Checks

Validates that all schema naming conventions are
followed: namespace casing and length,
node/generic names in PascalCase,
attribute/relationship names in snake_case, and
kind derivation as namespace+name concatenation.

## Why it matters

Naming convention violations are not stylistic —
`infrahubctl schema check` rejects the entire
schema bundle when any node breaks the regex, so
one underscore in a node name blocks the whole
load and every other change in the same branch
sits unmergeable until the offender is fixed. The
kind-derivation rule (`kind == namespace + name`)
is the most confusing variant because the user
"set the kind" explicitly and the platform
silently ignores it, derived value wins, and
relationships referencing the typed-in kind fail
to resolve. Catching these at audit time saves
the round trip through `infrahubctl` output that
points at line numbers rather than at the
underlying convention.

## Checks

1. **Namespace**: matches `^[A-Z][a-z0-9]+$`, 3-32 characters
2. **Node/Generic name**: matches `^[A-Z][a-zA-Z0-9]+$`, 2-32 characters
3. **Attribute names**: match `^[a-z0-9_]+$`, 3-32 characters
4. **Relationship names**: match `^[a-z0-9_]+$`, 3-32 characters
5. **Kind**: equals Namespace + Name concatenation
   (e.g., namespace `Infra` + name `Device` = kind
   `InfraDevice`)

## Common Issues

- Namespace starting with lowercase
- Node names with underscores (should be PascalCase)
- Attribute names with uppercase letters (should be snake_case)
- Kind not matching namespace + name
