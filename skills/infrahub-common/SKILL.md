---
name: infrahub-common
description: >-
  Shared references and cross-cutting rules used by all
  Infrahub skills. Contains GraphQL query syntax, .infrahub.yml
  configuration format, and common rules for git integration,
  display label caching, and Python environment setup.
  DO NOT TRIGGER directly — loaded automatically by other
  Infrahub skills when they need shared references.
user-invocable: false
metadata:
  version: 1.1.0
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
- **`rules/`** — Cross-cutting rules shared across skills:
  - Caching display labels in queries
  - Python environment and connectivity checks
  - Git integration and deployment patterns
  - Generated file protocol conventions
