---
title: Common Check Patterns
impact: MEDIUM
tags: patterns, error-collection, shared-utilities, scoped-validation
---

## Common Check Patterns

Impact: MEDIUM

Collect findings into local lists during traversal,
then emit them through `log_error` / `log_info` at
the end; share data-shaping helpers in a `common.py`
module; for large global checks, bucket records by
parent before validating.

### Why it matters

Interleaving `log_error` calls with the traversal
makes failure ordering depend on dict iteration and
makes it hard to add a "summary" log line — collecting
first lets the check report a deterministic count and
group related messages. Sharing helpers in
`checks/common.py` keeps each check focused on its
rule rather than re-implementing GraphQL response
unwrapping, which is where subtle bugs (treating a
node as a list, missing the `edges` wrapper) creep in.
Bucketing by parent turns an O(n²) cross-check into
O(n) per group — relevant when a global check sweeps
thousands of devices on every proposed change.

### Collecting Errors Before Logging

```python
def validate(self, data: dict) -> None:
    errors = []
    warnings = []

    for item in data["MyNode"]["edges"]:
        if bad_condition:
            errors.append(
                "Problem with "
                f"{item['node']['name']['value']}"
            )
        if mild_concern:
            warnings.append(
                "Note about "
                f"{item['node']['name']['value']}"
            )

    for warning in warnings:
        self.log_info(
            message=f"WARNING: {warning}"
        )

    for error in errors:
        self.log_error(message=error)
```

### Shared Utility Functions

```python
# checks/common.py
def clean_data(data):
    """Recursively normalize Infrahub API data."""
    # ... unwrap value/node/edges nesting ...

def get_data(data):
    """Extract first object from cleaned data."""
    cleaned = clean_data(data)
    first_key = next(iter(cleaned))
    first_value = cleaned[first_key]
    return (
        first_value[0]
        if isinstance(first_value, list)
        else first_value
    )
```

```python
# checks/my_check.py
from .common import get_data

class MyCheck(InfrahubCheck):
    query = "my_query"

    def validate(self, data: dict) -> None:
        device = get_data(data)
        # ... validate using cleaned data ...
```

### Scoped Validation (Performance)

For global checks on large datasets, group by parent
for efficient comparison:

```python
def validate(self, data: dict) -> None:
    edges = (
        data
        .get("DcimGenericDevice", {})
        .get("edges", [])
    )

    devices_by_rack = defaultdict(list)
    for edge in edges:
        device = edge["node"]
        rack_id = (
            device
            .get("rack", {})
            .get("node", {})
            .get("id")
        )
        if rack_id:
            devices_by_rack[rack_id].append(
                device
            )

    for rack_id, devices in (
        devices_by_rack.items()
    ):
        self._check_rack(devices)
```

Reference: [examples.md](../examples.md) for complete
check examples.
