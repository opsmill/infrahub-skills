# Infrahub Transform Reference

Class signatures, lifecycle, and registration shapes
for Python and Jinja2 transforms. The detailed rules
live in `rules/`; this file is the consolidated
quick-reference.

## Contents

- [Two Transform Kinds](#two-transform-kinds)
- [InfrahubTransform (Python) — Class API](#infrahubtransform-python--class-api)
- [Lifecycle: collect_data → transform → return](#lifecycle-collect_data--transform--return)
- [Return Type Drives `content_type`](#return-type-drives-content_type)
- [Jinja2-Only Transform](#jinja2-only-transform)
- [Hybrid Python + Jinja2](#hybrid-python--jinja2)
- [.infrahub.yml Registration](#infrahubyml-registration)
- [Testing Locally](#testing-locally)
- [Filter Environment (Jinja2)](#filter-environment-jinja2)

---

## Two Transform Kinds

| Kind | Output | Entry point | Registers under |
| ---- | ------ | ----------- | --------------- |
| **Python** | `dict` or `str` | `InfrahubTransform.transform()` | `python_transforms:` |
| **Jinja2** | `str` (text) | `.j2` template file | `jinja2_transforms:` |
| **Hybrid** | `str` (text) | Python `transform()` that renders Jinja2 | `python_transforms:` |

A transform is "hybrid" if the entry point is a
Python class — even when most of the work is in a
template. Registration follows the entry point: only
pure-template transforms go under `jinja2_transforms:`.

---

## InfrahubTransform (Python) — Class API

```python
from infrahub_sdk.transforms import InfrahubTransform


class MyTransform(InfrahubTransform):
    query = "my_query"          # Required. Matches queries[].name in .infrahub.yml
    timeout = 60                # Optional. Seconds. Default: 60

    async def transform(self, data: dict) -> dict | str:
        # data is the parsed GraphQL response
        return {"result": "..."}
```

### Class attributes

| Attribute | Type | Required | Description |
| --------- | ---- | -------- | ----------- |
| `query` | `str` | **Yes** | Name of a query registered under `queries:` in `.infrahub.yml` |
| `timeout` | `int` | No | Per-run timeout in seconds (default 60) |

### Instance properties (populated by the SDK)

| Property | Type | Notes |
| -------- | ---- | ----- |
| `self.client` | `InfrahubClient` | Use for additional reads inside `transform()` |
| `self.nodes` | `list[InfrahubNode]` | Hydrated objects from the query |
| `self.store` | `NodeStore` | Same nodes, indexed by id/hfid |
| `self.branch_name` | `str` | Branch the transform is running against |
| `self.root_directory` | `str` | Repo root on disk — use for loading Jinja2 templates |
| `self.server_url` | `str` | Infrahub server URL |

### Methods

| Method | Description |
| ------ | ----------- |
| `transform(data) -> Any` | **Implement this.** Sync or async — the SDK supports both. |
| `async collect_data()` | Runs the registered query. Called automatically by `run()`. |
| `async run(data=None)` | Orchestrates `collect_data()` then `transform()`. Don't override unless you need a custom data source. |

Don't shadow `self.client` / `self.store` / `self.nodes`
in `__init__` — the SDK populates them before `run()`
calls `transform()`, and shadowing leaves `transform`
with stale or `None` values.

---

## Lifecycle: collect_data → transform → return

```
SDK calls run()
  → collect_data() — runs the query named in `query`
  → self.nodes / self.store populated
  → transform(data) — your code runs here
  → return value bubbles up to the artifact pipeline
```

If the query name doesn't match anything in
`.infrahub.yml`, `collect_data()` skips silently and
`transform()` is called with `data=None` — the
canonical "I get None back" symptom.

---

## Return Type Drives `content_type`

| Return type | Suitable `artifact_definitions.content_type` |
| ----------- | -------------------------------------------- |
| `dict` | `application/json` |
| `str` | `text/plain` / `text/markdown` / `text/csv` / `application/yaml` / `application/xml` / `application/hcl` / `image/svg+xml` |

Mismatched return + content_type writes the wrong
shape into the artifact. The server enforces
`content_type` against a closed enum of 8 values —
`text/yaml` is **not** one of them; use
`application/yaml`. See
[rules/artifacts-definitions.md](./rules/artifacts-definitions.md).

---

## Jinja2-Only Transform

No Python file at all — the `.j2` template renders
directly against the query response.

```jinja2
{# templates/device_config.j2 #}
{% for edge in data["DcimDevice"]["edges"] %}
{% set d = edge.node %}
hostname {{ d.name.value }}
!
{% for intf in d.interfaces.edges %}
interface {{ intf.node.name.value }}
  description {{ intf.node.description.value | default("") }}
{% endfor %}
{% endfor %}
```

`data` is the raw GraphQL response — attributes are
under a `value` wrapper (`d.name.value`, not
`d.name`).

---

## Hybrid Python + Jinja2

The Python class prepares the data and picks the
template; Jinja2 renders. Registered as
`python_transforms:` (the entry point is the class).

```python
from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader
from netutils.utils import jinja2_convenience_function


class SpineConfig(InfrahubTransform):
    query = "spine_config"

    async def transform(self, data: dict) -> str:
        device = data["DcimDevice"]["edges"][0]["node"]
        platform = device["platform"]["node"]["name"]["value"]

        env = Environment(
            loader=FileSystemLoader(f"{self.root_directory}/templates/spines"),
            autoescape=False,
        )
        env.filters.update(jinja2_convenience_function())

        template = env.get_template(f"{platform}.j2")

        return template.render(
            hostname=device["name"]["value"],
            interfaces=device["interfaces"]["edges"],
        )
```

Use the hybrid pattern when:

- Selecting one of several templates by platform/role
- Pre-shaping the GraphQL response into a cleaner dict for the template
- Using filters or transforms that aren't in the SDK Jinja2 allowlist (see below)

---

## .infrahub.yml Registration

```yaml
queries:
  - name: spine_config
    file_path: queries/config/spine.gql

# Python or Hybrid transform — query lives on the class
python_transforms:
  - name: spine
    class_name: SpineConfig
    file_path: transforms/spine.py

# Pure Jinja2 transform — query must be declared HERE, not on a class
jinja2_transforms:
  - name: device_config
    query: spine_config              # Required for Jinja2-only
    template_path: templates/device_config.j2

artifact_definitions:
  - name: spine_config
    artifact_name: spine
    content_type: text/plain          # Matches transform's return type
    targets: spines                   # CoreStandardGroup name
    transformation: spine             # Matches python_transforms[].name
    parameters:
      device: name__value             # GraphQL $device = target's name
```

Key constraint: `jinja2_transforms` entries **require**
a top-level `query:` field. `python_transforms`
entries don't — the query is bound on the class via
`query = "..."`. Mixing them up is the most common
registration mistake.

---

## Testing Locally

```bash
# Render a Python transform end-to-end
infrahubctl transform spine device=spine-01

# Render a Jinja2 transform
infrahubctl render device_config device=spine-01

# Listing transforms registered in .infrahub.yml
infrahubctl transform --list
```

Local renders read the transform file off disk; they
don't require the repo to be registered as a
`CoreReadOnlyRepository`. That registration is what
enables the artifact pipeline — see
[rules/testing-commands.md](./rules/testing-commands.md)
for the lifecycle split.

---

## Filter Environment (Jinja2)

The SDK builds the Jinja2 `Environment` from an
explicit `AVAILABLE_FILTERS` allowlist plus netutils.
Both Ansible filters and several stdlib Jinja2
filters are absent — they fail at render time with
`No filter named 'X'`. See
[rules/jinja2-template.md](./rules/jinja2-template.md)
for the replacement table.

Reference: [Infrahub Transform Docs](https://docs.infrahub.app)
