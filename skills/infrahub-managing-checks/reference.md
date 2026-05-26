# Infrahub Check Reference

Class signatures, lifecycle, and the
`.infrahub.yml` registration shape for Infrahub
checks. Detailed rules live in `rules/`; this is
the consolidated quick-reference.

## Contents

- [What a Check Is](#what-a-check-is)
- [Two Check Variants: Global vs Targeted](#two-check-variants-global-vs-targeted)
- [InfrahubCheck — Class API](#infrahubcheck--class-api)
- [Logging: log_error / log_info (no log_warning)](#logging-log_error--log_info-no-log_warning)
- [Lifecycle: collect_data → validate → pass/fail count](#lifecycle-collect_data--validate--passfail-count)
- [.infrahub.yml Registration](#infrahubyml-registration)
- [Testing Locally](#testing-locally)

---

## What a Check Is

A check is data-quality validation that runs in the
proposed-change pipeline. Any `log_error()` call
inside `validate()` blocks the merge until a human
fixes the underlying data.

Three pieces:

1. **GraphQL query** (`.gql`) — fetches the data to validate
2. **Python class** (`InfrahubCheck` subclass) — implements `validate()`
3. **`.infrahub.yml` entry** under `check_definitions:`

---

## Two Check Variants: Global vs Targeted

| Variant | Runs | Has `targets:` | Has `parameters:` |
| ------- | ---- | -------------- | ----------------- |
| **Global** | Once per proposed change against all objects of a type | No | No |
| **Targeted** | Once per group member, with per-object query variables | Yes (`CoreStandardGroup`) | Yes (maps target attrs → GraphQL `$var`) |

A targeted check is the right shape when the
validation needs per-object context (e.g., "for each
leaf device, check that its uplinks are correctly
provisioned"). Global is the right shape for
data-quality sweeps ("no two devices in the same
rack at the same RU").

---

## InfrahubCheck — Class API

```python
from infrahub_sdk.checks import InfrahubCheck


class MyCheck(InfrahubCheck):
    query = "my_query"          # Required. Matches queries[].name in .infrahub.yml
    timeout = 60                # Optional. Seconds. Default: 60

    def validate(self, data: dict) -> None:
        # data is the unpacked GraphQL response (the "data" key already stripped)
        ...
```

### Class attributes

| Attribute | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `query` | `str` | **Yes** | Name of a query registered under `queries:` in `.infrahub.yml` |
| `timeout` | `int` | No | Per-run timeout in seconds (default 60) |

### Instance properties (populated by the SDK)

| Property | Type | Description |
| -------- | ---- | ----------- |
| `self.client` | `InfrahubClient` | Use for additional reads inside `validate()` |
| `self.branch_name` | `str` | Branch the check is running against |
| `self.root_directory` | `str` | Repo root on disk |
| `self.params` | `dict` | Query parameters bound from `targets`/`parameters` (targeted checks) |
| `self.passed` | `bool` | True if no `log_error()` was called; set after `run()` |
| `self.logs` | `list[dict]` | All log entries |
| `self.errors` | `property` | Filter of `self.logs` to ERROR-level entries |

### Methods

| Method | Description |
| ------ | ----------- |
| `validate(data) -> None` | **Implement this.** Sync or async — the SDK supports both. |
| `log_error(message, object_id=None, object_type=None)` | Record a failure — any call here marks the check failed. |
| `log_info(message, object_id=None, object_type=None)` | Record an informational message — does **not** affect pass/fail. |
| `async collect_data()` | Runs the registered query. Called automatically by `run()`. |
| `async run()` | Orchestrates `collect_data()` → `validate()` → pass/fail decision. Don't override. |

---

## Logging: log_error / log_info (no log_warning)

```python
def validate(self, data: dict) -> None:
    for edge in data.get("DcimDevice", {}).get("edges", []):
        node = edge["node"]
        if node["status"]["value"] != "active":
            self.log_error(
                message=f"Device {node['name']['value']} is not active",
                object_id=node["id"],
                object_type=node["__typename"],
            )
        else:
            self.log_info(
                message=f"Device {node['name']['value']} passed",
                object_id=node["id"],
            )
```

| Call | Effect on pass/fail | Use for |
| ---- | ------------------- | ------- |
| `self.log_error(...)` | **Fails the check** — blocks the proposed change | Validation failures |
| `self.log_info(...)` | No effect | Audit trail, "checked X" messages |

There is **no `log_warning()` method**. Reaching for
it raises `AttributeError` and the check fails with
a traceback rather than the intended validation
message. For non-failing warnings, use `log_info()`
with a `"WARNING:"` prefix.

Always include `id` and `__typename` in the GraphQL
selection so error logs carry both — `__typename`
returns the **concrete kind**, not the generic the
fragment matched on (see
[../infrahub-common/graphql-queries.md](../infrahub-common/graphql-queries.md#inline-fragments-populate-fields-but-__typename-returns-the-concrete-kind)).

---

## Lifecycle: collect_data → validate → pass/fail count

```
Dispatcher invokes run()
  → collect_data() executes the registered query
  → the outer "data" key is unwrapped
  → validate(data) runs your code
      → log_error(...) / log_info(...) record results
  → after validate() returns, the SDK counts ERROR-level logs
      → 0 errors → self.passed = True
      → 1+ errors → self.passed = False, merge blocked
```

The `data` argument to `validate()` is already
unwrapped — indexing as `data["data"]["..."]` returns
`None` and silently passes every assertion. Index
straight to the kind name:
`data["DcimDevice"]["edges"]`.

---

## .infrahub.yml Registration

```yaml
queries:
  - name: rack_devices
    file_path: queries/rack_devices.gql

check_definitions:
  # Global check
  - name: rack_unit_collision
    file_path: checks/rack_unit_collision.py
    class_name: RackUnitCollision

  # Targeted check
  - name: leaf_validation
    file_path: checks/leaf.py
    class_name: LeafValidation
    targets: leaf_devices             # CoreStandardGroup name
    parameters:
      device: name__value             # GraphQL $device = target's name
```

> **`check_definitions` does NOT accept a `query:`
> field.** The model has `extra="forbid"`, so adding
> `query:` here fails the whole repo config with a
> Pydantic ValidationError. The query is bound on
> the class via `query = "..."`. This is the
> opposite of `generator_definitions:`, which
> *requires* a top-level `query:` field — see
> [rules/registration-config.md](./rules/registration-config.md)
> for the side-by-side comparison.

Allowed fields under each `check_definitions` entry:
`name`, `file_path`, `class_name`, `targets`,
`parameters`. Anything else raises
`extra_forbidden`.

---

## Testing Locally

```bash
# Run a check against the current branch
infrahubctl check my_check

# Run against a specific branch
infrahubctl check my_check --branch test-feature

# List checks registered in .infrahub.yml
infrahubctl check --list
```

Local runs hit the same SDK path as the pipeline, so
a successful local run means the pipeline will
behave the same way against the same branch state.

See [rules/testing-commands.md](./rules/testing-commands.md)
for the full command surface and
[rules/patterns-common.md](./rules/patterns-common.md)
for shared utilities across checks.

Reference: [Infrahub Check Docs](https://docs.infrahub.app)
