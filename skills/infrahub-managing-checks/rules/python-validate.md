---
title: Python Check Class and Validation
impact: CRITICAL
tags: python, validate, log_error, log_info, InfrahubCheck
---

## Python Check Class and Validation

Impact: CRITICAL

The `validate()` method is where all check logic lives.
Understanding logging behavior is essential --
`log_error()` causes failure, `log_info()` is safe.

### Basic Structure

```python
from infrahub_sdk.checks import InfrahubCheck


class MyCheck(InfrahubCheck):
    query = "my_query"  # Must match .infrahub.yml

    def validate(self, data: dict) -> None:
        edges = (
            data
            .get("MyNodeKind", {})
            .get("edges", [])
        )

        for edge in edges:
            node = edge["node"]

            if something_is_wrong:
                self.log_error(
                    message="Problem description",
                    object_id=node["id"],
                    object_type=(
                        node["__typename"]
                    ),
                )

            self.log_info(
                message="Everything looks good"
            )
```

### Logging Rules

<!-- markdownlint-disable MD013 -->

| Method | Effect | Use For |
| ------ | ------ | ------- |
| `self.log_error(message, object_id=None, object_type=None)` | **Causes check to FAIL** | Validation failures |
| `self.log_info(message, object_id=None, object_type=None)` | No effect on pass/fail | Informational messages |

<!-- markdownlint-enable MD013 -->

There is no `log_warning()` method. Use `log_info()`
with a "WARNING:" prefix for non-failing warnings.

### Key Rules

- `validate()` can be sync or async -- the SDK handles
  both
- Always include `id` and `__typename` in your GraphQL
  query for error logging
- Any `log_error()` call means the proposed change
  cannot merge
- The `data` parameter is the unpacked GraphQL response
  (the `"data"` key is already extracted)

Reference:
[Infrahub Check Docs](https://docs.infrahub.app)
