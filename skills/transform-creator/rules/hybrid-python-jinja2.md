---
title: Hybrid Python + Jinja2 Pattern
impact: HIGH
tags: hybrid, python, jinja2, FileSystemLoader, platform-specific
---

## Hybrid Python + Jinja2 Pattern

**Impact:** HIGH

For complex scenarios, use Python to prepare data and
Jinja2 to render it. This is the most common pattern
for device configuration generation.

### Example: Platform-Specific Config

```python
from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader
from netutils.utils import jinja2_convenience_function
from .common import get_data, get_interfaces, get_bgp_profile


class Spine(InfrahubTransform):
    query = "spine_config"

    async def transform(self, data: dict) -> str:
        data = get_data(data)

        # Get platform for template selection
        platform = data["device_type"]["platform"]["netmiko_device_type"]

        # Set up Jinja2 with template directory
        template_path = f"{self.root_directory}/templates/configs/spines"
        env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=False,
        )
        env.filters.update(jinja2_convenience_function())

        # Select platform-specific template
        template = env.get_template(f"{platform}.j2")

        # Prepare template context
        config = {
            "hostname": data.get("name"),
            "bgp": get_bgp_profile(data.get("device_services")),
            "interfaces": get_interfaces(data.get("interfaces")),
        }

        return template.render(**config)
```

### Key Points

- **`self.root_directory`** provides the repo root path for template loading
- **`jinja2_convenience_function()`** adds netutils
  filters to the Jinja2 environment
- **Platform-specific templates** selected dynamically
  based on query data
- **Registered as a `python_transform`** in
  `.infrahub.yml` (not `jinja2_transform`)

Reference: [examples.md](../examples.md) for complete hybrid examples.
