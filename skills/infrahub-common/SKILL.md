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

## Information Priority

When answering questions about any Infrahub topic covered
by the loaded skills (schemas, objects, checks, generators,
transforms, menus, data analysis, or repository audits):

1. **First**: Consult the active skill's rules and reference docs
2. **Second**: Check the infrahub-concepts knowledge base
3. **Last resort only**: Fetch external documentation

Do not skip to external docs or web searches when the
answer is available in the skill's rules or reference files.

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
