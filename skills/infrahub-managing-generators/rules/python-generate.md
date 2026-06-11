---
title: Python Generator Class and Object Creation
impact: CRITICAL
tags: python, generate, create, save, allow_upsert, async
---

## Python Generator Class and Object Creation

Impact: CRITICAL

`generate()` is the only method the dispatcher calls
on a generator; it is async, takes the GraphQL
result as `data`, and creates objects through
`self.client`.

### Why it matters

The whole tracking context is wired up around the
async `generate()` call. Defining it as a sync
method silently shadows the base class's coroutine
and the dispatcher awaits nothing — no objects get
created and no error is raised. Calling sync SDK
methods (or `time.sleep`, `requests.get`, etc.)
inside `generate()` blocks the worker's event loop
long enough to trigger a watchdog timeout, leaving
the proposed change in an inconsistent state.
`self.client` is the variant that emits tracking
metadata on every write; reaching for the raw
client bypasses the tracking group, so cleanup on
the next run won't find those objects.

### Basic Structure

```python
from infrahub_sdk.generator import InfrahubGenerator


class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        topology = (
            data["TopologyDataCenter"]["edges"]
            [0]["node"]
        )
        name = topology["name"]["value"]

        device = await self.client.create(
            kind="DcimDevice",
            data={
                "name": f"{name}-spine-01",
                "status": "active",
            }
        )
        await device.save(allow_upsert=True)
```

### Object Creation API

```python
# Create a new object
obj = await self.client.create(
    kind="DcimDevice",
    data={
        "name": "my-device",
        "status": "active",
        # Use ID for relationships
        "device_type": device_type_id,
    }
)
await obj.save(allow_upsert=True)

# Get an existing object
existing = await self.client.get(
    kind="LocationBuilding",
    name__value="PAR-1",
)

# Allocate from a pool
ip = await self.client.allocate_next_ip_address(
    resource_pool=pool,
    identifier=f"{device_name}-loopback",
)
```

### Critical Rules

- `generate()` is async; every client call needs
  `await` or the coroutine returns unresolved and
  the object is never saved.
- `save(allow_upsert=True)` makes the write
  idempotent — without it, the second run errors out
  on the first object that already exists and the
  rest of `generate()` never executes.
- Use `self.client` inside `generate()`; the raw
  client (`self._init_client`) skips tracking, so
  `delete_unused_nodes` can't reclaim those objects
  on the next run.
- Reference relationships by ID in the `data` dict;
  passing a display label triggers a slow lookup or
  fails outright when names aren't unique.
- Treat optional GraphQL fields defensively —
  `None` for a missing relationship is normal, and
  unguarded `["value"]` access raises `TypeError`
  partway through the run.

Reference:
[Infrahub Generator Docs](https://docs.infrahub.app)
