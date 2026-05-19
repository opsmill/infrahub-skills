---
title: Python Generator Class and Object Creation
impact: CRITICAL
tags: python, generate, create, save, allow_upsert, async
---

## Python Generator Class and Object Creation

Impact: CRITICAL

The `generate()` method must be async. Use `self.client`
for all object operations inside it.

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

- `generate()` must be async -- use `await` for all
  client operations
- Always use `allow_upsert=True` on `save()` for
  idempotent create-or-update
- Use `self.client` (not `self._init_client`) inside
  `generate()` -- it has tracking enabled
- Use IDs for relationship references in `data` dict
- Handle empty/missing data gracefully -- GraphQL may
  return `None` for optional fields

Reference:
[Infrahub Generator Docs](https://docs.infrahub.app)
