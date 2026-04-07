---
title: InfrahubCheck API Reference
impact: HIGH
tags: api, class-attributes, properties, methods, lifecycle
---

## InfrahubCheck API Reference

Impact: HIGH

### Class Attributes

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `query` | `str` | **Required.** Name of the GraphQL query |
| `timeout` | `int` | Timeout in seconds (default: 60) |

### Instance Properties

| Property | Type | Description |
| -------- | ---- | ----------- |
| `self.client` | `InfrahubClient` | SDK client for API calls |
| `self.branch_name` | `str` | Current branch name |
| `self.root_directory` | `str` | Repository root path |
| `self.params` | `dict` | Query parameters |
| `self.passed` | `bool` | Whether check passed (set after `run()`) |
| `self.logs` | `list[dict]` | All log entries |
| `self.errors` | property | Filtered ERROR-level logs |

### Methods

<!-- markdownlint-disable MD013 -->

| Method | Description |
| ------ | ----------- |
| `validate(data: dict) -> None` | **You must implement this.** Can be sync or async. |
| `log_error(message, object_id=None, object_type=None)` | Log a validation error (causes check to FAIL) |
| `log_info(message, object_id=None, object_type=None)` | Log an informational message (does NOT cause failure) |

<!-- markdownlint-enable MD013 -->

### Execution Lifecycle

1. `collect_data()` -- executes the GraphQL query
2. Unpacks the `"data"` key from the response
3. Calls your `validate(data)` method
4. Counts ERROR-level logs -- if zero errors, check passes

Reference:
[Infrahub SDK Docs](https://docs.infrahub.app)
