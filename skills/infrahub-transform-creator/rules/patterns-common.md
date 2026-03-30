---
title: Common Transform Patterns
impact: MEDIUM
tags: patterns, data-extraction, csv, common-py
---

## Common Transform Patterns

**Impact:** MEDIUM

### Data Extraction Utilities

```python
# transforms/common.py
def get_data(data):
    """Extract first object from GraphQL response."""
    cleaned = clean_data(data)
    first_key = next(iter(cleaned))
    return cleaned[first_key][0]

def get_interfaces(interfaces):
    """Return sorted interface list."""
    if not interfaces:
        return []
    return sorted(interfaces, key=lambda x: x.get("name", ""))

def get_bgp_profile(services):
    """Group BGP sessions by peer group."""
    if not services:
        return []
    return [s for s in services if s.get("typename") == "ServiceBGP"]
```

### CSV Output

```python
class CableMatrix(InfrahubTransform):
    query = "topology_cabling"

    async def transform(self, data: dict) -> str:
        rows = ["Source Device,Source Interface,Remote Device,Remote Interface"]

        for device in data["Topology"]["edges"][0]["node"]["devices"]["edges"]:
            source = device["node"]["name"]["value"]
            for intf in device["node"]["interfaces"]["edges"]:
                cable = intf["node"].get("connector", {}).get("node")
                if cable:
                    # ... extract remote endpoint ...
                    rows.append(f"{source},{src_intf},{remote_device},{remote_intf}")

        return "\n".join(rows)
```

### Shared Utilities Pattern

Extract common data extraction into
`transforms/common.py` and import across transform
files:

```python
# transforms/spine.py
from .common import get_data, get_interfaces

class Spine(InfrahubTransform):
    query = "spine_config"

    async def transform(self, data: dict) -> str:
        data = get_data(data)
        interfaces = get_interfaces(data.get("interfaces"))
        # ... render config ...
```

Reference: [examples.md](../examples.md) for complete transform examples.
