---
name: infrahub-check-creator
description: >-
  Create and manage Infrahub check definitions. Use when
  writing validation logic, creating Python checks that run
  in proposed change pipelines, or building data quality
  guards for Infrahub.
metadata:
  version: 1.1.0
  author: OpsMill
---

# Infrahub Check Creator

## Overview

Expert guidance for creating Infrahub checks. Checks are
user-defined validation logic (Python + GraphQL) that run as
part of a proposed change pipeline. If a check logs any
errors, the proposed change cannot be merged.

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
   validate
2. **Python class** -- inherits from `InfrahubCheck`,
   implements `validate()`
3. **Configuration** -- declared in `.infrahub.yml` under
   `check_definitions`

```python
from infrahub_sdk.checks import InfrahubCheck


class MyCheck(InfrahubCheck):
    query = "my_query"  # Must match query name

    def validate(self, data: dict) -> None:
        # Validation logic here
        if something_is_wrong:
            self.log_error(
                message="Problem description"
            )
```

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
- **[../infrahub-schema-creator/SKILL.md](../infrahub-schema-creator/SKILL.md)**
  -- Schema definitions checks validate against
- **[rules/](./rules/)** -- Individual rules organized by
  category prefix
