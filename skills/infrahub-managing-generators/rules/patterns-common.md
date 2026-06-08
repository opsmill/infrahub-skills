---
title: Common Generator Patterns
impact: MEDIUM
tags: patterns, data-cleaning, batch-creation, local-store
---

## Common Generator Patterns

Impact: MEDIUM

A few patterns recur across nearly every generator:
unwrapping the nested GraphQL response, creating
objects in batches from design quantities, and
chaining created objects through subsequent calls.

### Why it matters

GraphQL responses are deeply wrapped
(`edges → node → value`); without a recursive
unwrap, generator code becomes a forest of
`["edges"][0]["node"]["value"]` chains that break
the moment the schema gains an extra layer. Batch
creation loops have to call `save(allow_upsert=True)`
inside the loop or the second run fails on the first
existing object and aborts before it touches the
rest. Passing freshly-created SDK objects directly
into the `data` dict of the next `create()` call
avoids a second round trip to look up the ID — and
keeps both objects in the same tracking group so
they get cleaned up together if the design changes.

### Data Cleaning Helper

```python
def clean_data(data):
    """Recursively unwrap value/node/edges."""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if set(value.keys()) == {"value"}:
                    result[key] = value["value"]
                elif "node" in value:
                    result[key] = clean_data(
                        value["node"]
                    )
                elif "edges" in value:
                    result[key] = clean_data(
                        value["edges"]
                    )
                else:
                    result[key] = clean_data(value)
            else:
                result[key] = clean_data(value)
        return result
    if isinstance(data, list):
        return [
            clean_data(item.get("node", item))
            for item in data
        ]
    return data
```

### Batch Object Creation

```python
async def generate(self, data: dict) -> None:
    for element in design["elements"]:
        quantity = element["quantity"]
        role = element["role"]

        for i in range(1, quantity + 1):
            device = await self.client.create(
                kind="DcimDevice",
                data={
                    "name": (
                        f"{topology_name}"
                        f"-{role}-{i:02d}"
                    ),
                    "role": role,
                    "status": "active",
                }
            )
            await device.save(allow_upsert=True)
```

### Using the Local Store

```python
async def generate(self, data: dict) -> None:
    site = await self.client.create(
        kind="LocationBuilding",
        data={"name": "PAR-1"},
    )
    await site.save(allow_upsert=True)

    device = await self.client.create(
        kind="DcimDevice",
        data={
            "name": "spine-01",
            # Pass the SDK object directly
            "location": site,
        }
    )
    await device.save(allow_upsert=True)
```

Reference: [examples.md](../examples.md) for complete
generator examples.
