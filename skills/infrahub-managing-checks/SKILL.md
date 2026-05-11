---
name: infrahub-managing-checks
description: >-
  Creates Infrahub check definitions — Python validation logic and GraphQL queries for proposed change pipelines.
  TRIGGER when: writing validation checks, creating Python checks, building data quality guards for proposed changes.
  DO NOT TRIGGER when: designing schemas, querying live data, building transforms or generators.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
argument-hint: "[check-name] [description...]"
metadata:
  version: 1.2.4
  author: OpsMill
---

# Infrahub Check Creator

## Overview

Expert guidance for creating Infrahub checks. Checks are
user-defined validation logic (Python + GraphQL) that run as
part of a proposed change pipeline. If a check logs any
errors, the proposed change cannot be merged.

## Project Context

Infrahub config:
!`cat .infrahub.yml 2>/dev/null || echo "No .infrahub.yml found"`

Existing checks:
!`find . -name "*.py" -path "*/checks/*" 2>/dev/null | head -20`

Existing queries:
!`find . -name "*.gql" -path "*/queries/*" 2>/dev/null | head -20`

## When to Use

- Writing validation logic for proposed changes
- Creating data quality guards (e.g., rack collision
  detection)
- Building global checks that validate all objects of a type
- Building targeted checks that validate specific grouped
  objects
- Debugging check failures or understanding the check
  lifecycle

## Rule Categories

<!-- markdownlint-disable MD013 -->

| Priority | Category | Prefix | Description |
| -------- | -------- | ------ | ----------- |
| CRITICAL | Architecture | `architecture-` | Three components, global vs targeted, execution flow |
| CRITICAL | Python Class | `python-` | InfrahubCheck base class, validate(), log_error/log_info |
| HIGH | API Reference | `api-` | Class attributes, instance properties, methods, lifecycle |
| HIGH | Registration | `registration-` | .infrahub.yml config, query name matching, parameters |
| MEDIUM | Patterns | `patterns-` | Error collection, shared utilities, scoped validation |
| LOW | Testing | `testing-` | infrahubctl check commands, branch testing |

<!-- markdownlint-enable MD013 -->

## Check Basics

Every check has three components:

1. **GraphQL query** (`.gql` file) -- fetches the data to
   validate, and is registered under the top-level
   `queries:` section of `.infrahub.yml`
2. **Python class** -- inherits from `InfrahubCheck`,
   sets `query = "<query_name>"`, implements
   `validate()`
3. **Configuration** -- declared in `.infrahub.yml` under
   `check_definitions` (which does **not** take a
   `query:` field — see below)

```python
from infrahub_sdk.checks import InfrahubCheck


class MyCheck(InfrahubCheck):
    query = "my_query"  # Must match queries[].name in .infrahub.yml

    def validate(self, data: dict) -> None:
        # Validation logic here
        if something_is_wrong:
            self.log_error(
                message="Problem description"
            )
```

> **Where the query is bound:** the Python class
> (`query = "..."`), not `check_definitions`. The
> repository config model uses `extra="forbid"`, so
> putting `query:` under `check_definitions:` makes
> the whole repo config fail validation. This is the
> #1 confusion vs. `generator_definitions:`, which
> *does* take a top-level `query:`. See
> [rules/registration-config.md](./rules/registration-config.md).

## Workflow

Follow these steps when creating a check:

1. **Understand the validation goal** — What data
   condition should block a proposed change? Determine
   whether this is a global check (all objects of a
   type) or targeted (specific group). Read
   [rules/architecture-types.md](./rules/architecture-types.md).
2. **Write the GraphQL query** — Create a `.gql` file
   that fetches the data to validate. Read
   [../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)
   for query patterns.
3. **Implement the Python class** — Inherit from
   `InfrahubCheck`, implement `validate()`. Read
   [rules/python-validate.md](./rules/python-validate.md)
   for the class pattern and
   [rules/api-reference.md](./rules/api-reference.md)
   for available methods.
4. **Register in .infrahub.yml** — Add the check under
   `check_definitions`. The query name must match the
   Python class `query` attribute. See
   [rules/registration-config.md](./rules/registration-config.md).
5. **Test** — Run `infrahubctl check` to validate. See
   [rules/testing-commands.md](./rules/testing-commands.md).

## Supporting References

- **[examples.md](./examples.md)** -- Complete check
  patterns (global, targeted, minimal)
- **[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md)**
  -- GraphQL query writing reference
- **[../infrahub-common/infrahub-yml-reference.md](../infrahub-common/infrahub-yml-reference.md)**
  -- .infrahub.yml project configuration
- **[../infrahub-common/rules/](../infrahub-common/rules/)** -- Shared rules
  (git integration, caching gotchas) that apply across all
  skills
- **[../infrahub-managing-schemas/SKILL.md](../infrahub-managing-schemas/SKILL.md)**
  -- Schema definitions checks validate against
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
