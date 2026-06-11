---
name: infrahub-common
description: >-
  Shared references and cross-cutting rules for all Infrahub skills — GraphQL syntax, .infrahub.yml format, and common patterns.
  DO NOT TRIGGER directly — loaded automatically by other Infrahub skills when they need shared references.
user-invocable: false
metadata:
  version: 1.2.6
  author: OpsMill
---

# Infrahub Common References

This skill contains shared resources referenced by all other
Infrahub skills. It is not meant to be invoked directly.

## Contents

- **`graphql-queries.md`** — Infrahub GraphQL query syntax,
  filters, nested queries, and pagination patterns
- **`infrahub-yml-reference.md`** — `.infrahub.yml`
  configuration file format and field reference
- **`netbox-vs-infrahub.md`** — Field-by-field
  migration appendix for engineers porting NetBox
  queries, templates, or overlay data
- **`metadata-lineage.md`** — Value metadata (`source`,
  `owner`, `is_protected`): what each field means, how
  to set it in object files, and why `source` does not
  control edit access
- **`rules/`** — Cross-cutting rules shared across skills:
  - Caching display labels in queries
  - Python environment and connectivity checks
  - Git integration and deployment patterns
  - Recovery from partial repository syncs
  - Generated file protocol conventions
