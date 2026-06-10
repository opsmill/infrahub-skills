---
title: xref-query-names
impact: HIGH
tags: audit, cross-references, queries
---

# Rule: xref-query-names

**Severity**: HIGH
**Category**: Cross-References

## What It Checks

Validates that query names line up across the
three places they appear: the `query` class
attribute on the Python component, the `name`
field of the matching `.infrahub.yml` `queries`
entry, and the `query` field on any
`jinja2_transforms` block that references it.

## Why it matters

Query name mismatches are runtime failures, not
load-time failures — the platform happily imports
the check, generator, or transform with its
typo'd `query = "my_query_v2"`, and the error
surfaces only when the proposed-change pipeline
tries to resolve the name and raises "query not
found", usually on the first run after deploy.
The blast radius depends on where the typo
landed: a check fails the proposed change with a
red mark, a transform breaks artifact generation
for every device, a generator silently produces
nothing. Catching the mismatch at audit time
moves the failure from "runs in production" to
"fixable before merge". Orphan-query detection
also keeps `.infrahub.yml` clean — unused entries
accumulate over refactors and confuse later
maintainers about which queries are actually
live.

## Checks

1. Every `query` class attribute in a
   check/generator/transform Python file matches a
   `name` in the `queries` section of `.infrahub.yml`
2. Every `query` field in `jinja2_transforms` matches
   a query `name`
3. Every query registered in `.infrahub.yml` is
   actually used by at least one component (orphan
   query detection)
4. The `.gql` file content is valid GraphQL syntax

## Common Issues

- Python class has `query = "my_query"` but `.infrahub.yml` has `name: my_query_v2`
- Query registered but never referenced by any check, transform, or generator
- Typo in query name causing runtime "query not found" errors
