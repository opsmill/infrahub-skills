---
title: Python Transform Class
impact: CRITICAL
tags: python, InfrahubTransform, transform, return-types
---

## Python Transform Class

**Impact:** CRITICAL

Python transforms inherit from `InfrahubTransform` and
implement a `transform()` method that returns the
transformed data.

### Basic Structure

```python
from infrahub_sdk.transforms import InfrahubTransform


class MyTransform(InfrahubTransform):
    query = "my_query"                    # Must match query name in .infrahub.yml

    async def transform(self, data: dict) -> dict:
        device = data["DcimDevice"]["edges"][0]["node"]

        return {
            "hostname": device["name"]["value"],
            "role": device["role"]["value"],
            "interfaces": [
                intf["node"]["name"]["value"]
                for intf in device["interfaces"]["edges"]
            ],
        }
```

### Return Types

| Return Type | Content Type       | Use Case                      |
| ----------- | ------------------ | ----------------------------- |
| `dict`      | `application/json` | Structured data, API payloads |
| `str`       | `text/plain`       | Device configs, scripts, CSV  |

### Registration in .infrahub.yml

```yaml
queries:
  - name: my_query
    file_path: queries/config/my_query.gql

python_transforms:
  - name: my_transform
    class_name: MyTransform
    file_path: transforms/my_transform.py
```

### Key Rules

- **`query` class attribute must match** the query `name` in `.infrahub.yml`
- **`transform()` can be sync or async** -- the SDK handles both
- **Return type determines format** -- `dict` for JSON, `str` for text
- **Use `self.root_directory`** to access templates and other repo files

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
