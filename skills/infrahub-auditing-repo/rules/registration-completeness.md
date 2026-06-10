---
title: registration-completeness
impact: HIGH
tags: audit, registration, infrahub-yml
---

# Rule: registration-completeness

**Severity**: HIGH
**Category**: Registration

## What It Checks

Ensures every Python check, generator, transform,
GraphQL query, Jinja template, schema file, object
file, and menu file is registered in
`.infrahub.yml`, and that no orphan files sit
under those directories without a registration
entry.

## Why it matters

Infrahub only loads what `.infrahub.yml` declares
— a Python file containing an `InfrahubCheck`
subclass that isn't listed under
`check_definitions` is dead code that the platform
never imports, so the check never runs on
proposed changes and silently fails to enforce
whatever invariant the author wrote it for. The
failure mode is invisible: no error, no warning,
just absence. Orphan queries and templates are
the same shape — they sit in the repo, pass code
review, and protect nothing. Catching this at
audit time is the only realistic way to find the
gap, because there's nothing in the running
platform that signals "this file should be
loaded but isn't".

## Checks

1. All Python files containing `InfrahubCheck`,
   `InfrahubGenerator`, or `InfrahubTransform`
   subclasses are registered in the appropriate
   `.infrahub.yml` section
2. All `.gql` files are referenced by a `queries` entry
3. All Jinja2 templates (`.j2` files) are referenced by a `jinja2_transforms` entry
4. Schema files are under a path listed in `schemas:`
5. Object files are under a path listed in `objects:`
6. Menu files are listed under `menus:`
7. No orphan Python/query/template files that aren't registered

## Common Issues

- New Python check file created but not added to `check_definitions`
- Query `.gql` file not registered in `queries` section
- Jinja2 template created but not linked via `jinja2_transforms`
- Schema file outside the `schemas:` directory path
