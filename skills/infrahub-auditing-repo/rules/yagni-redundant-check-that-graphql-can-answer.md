---
title: yagni-redundant-check-that-graphql-can-answer
impact: MEDIUM
ladder_step: 6
tags: audit, yagni, check, graphql
---

# Rule: yagni-redundant-check-that-graphql-can-answer

**Severity**: MEDIUM
**Category**: YAGNI / Cost-to-Fix
**Ladder step**: 6 — Can a GraphQL query + thin assertion replace the check?

## What It Checks

Python checks whose entire logic is "run a GraphQL query and raise
if the result count is wrong." The query already does the work; the
Python wrapper adds boilerplate without adding judgment.

## Why it matters

When the logic is `count == 0 → pass, count > 0 → fail`, the query
itself is the test. Wrapping it in 30-50 lines of `InfrahubCheck`
plumbing buries the intent inside SDK machinery, doubles the surface
area for naming drift between `.gql` and `.infrahub.yml`, and makes
the check harder to read in code review. The thin form — `.gql` file
plus five lines of Python — keeps the assertion visible at the top
of the file.

## Checks

1. Check class whose `validate` method only does:
   `for item in data["...nodes"]: self.log_error(...)`. Trim to one
   loop, one log call, one return.
2. Check whose entire `validate` body is wrapping the query's
   `count` or list length in a comparison. Replace with the count
   check inline.
3. Check that imports utility functions only to format
   `f"Found {n} bad rows"`. The query result already has the rows;
   the check is a thin transformer, not a validator.
4. Check that re-queries Infrahub from inside `validate` (extra HTTP
   calls) when the GraphQL query passed by the pipeline already
   contains the answer.

## What NOT to flag

- Checks that combine multiple GraphQL results (cross-collection
  reconciliation). Those genuinely need code.
- Checks that compare against an external source of truth (LDAP,
  spreadsheet, vendor API). The Python wrapper is doing work.
- Checks that compute derived quantities (sums, distinct counts
  across nested relationships) GraphQL can't express directly.

## Common Issues

- A 60-line check whose `validate` is `if len(data) > 0: raise`.
  The GraphQL filter is the assertion; the Python is decoration.
- A check that queries twice — once via the pipeline-provided
  GraphQL query and once via `self.client.query()`. The second call
  is almost always unnecessary.
- Multiple checks sharing the same query and differing only in the
  error message. Consolidate into one check or push the variation
  into the query itself.
