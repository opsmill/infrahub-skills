---
title: Python Transform Class
impact: CRITICAL
tags: python, InfrahubTransform, transform, return-types
---

## Python Transform Class

Impact: CRITICAL

A Python transform is a subclass of `InfrahubTransform`
with a `query` class attribute and a `transform()`
method whose return type drives the artifact's
`content_type`.

### Why it matters

The SDK wires three things together by convention: the
`query` attribute points at a named query in
`.infrahub.yml`, the `transform()` method receives that
query's GraphQL response as `data`, and the return
value's Python type decides whether downstream
artifacts are served as JSON or plain text. A mismatch
on any of the three breaks the pipeline differently —
a wrong `query` name surfaces as a missing-query error
at sync, but a `dict` return paired with a
`text/plain` artifact definition writes a stringified
Python dict into the artifact, which looks valid but
is unusable by any downstream consumer expecting JSON.

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

- The `query` class attribute resolves by exact name
  against `.infrahub.yml`; a mismatch fails at sync
- `transform()` can be sync or async -- the SDK
  handles both
- Return type determines artifact format -- `dict`
  yields JSON, `str` yields text
- `self.root_directory` is the repository root, used
  for loading templates and sibling files

### `Kind: JSON` Attributes in GraphQL Responses

`kind: JSON` attributes are serialised through
GraphQL's `GenericScalar`, so `value` arrives as a
real Python `dict` / `list` — index into it
directly:

```python
async def transform(self, data: dict) -> dict:
    device = data["DcimDevice"]["edges"][0]["node"]
    config = device["local_config"]["value"]   # already a dict
    return {"vlans": config["vlans"]}
```

External consumers that re-template the same
attribute (e.g. an Ansible inventory plugin's
`compose:` pipeline) can stringify it to a repr —
in that case the unwrap (`| from_yaml` or
`| from_json`) belongs in that pipeline, not in
this transform.

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
