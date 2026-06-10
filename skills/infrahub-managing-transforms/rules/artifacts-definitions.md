---
title: Artifact Definitions
impact: HIGH
tags: artifacts, content-type, targets, CoreArtifactTarget
---

## Artifact Definitions

Impact: HIGH

Each entry in `artifact_definitions` binds a
transform name to a target group and a content type;
the binding is by string match, not reference.

### Why it matters

`transformation:` resolves by exact name against
either `python_transforms` or `jinja2_transforms` —
no namespace, no kind, just the name string — so a
typo or a stale rename surfaces as a "transformation
not found" error at artifact-render time, well after
the rest of the repo has synced cleanly. The
`content_type` is equally load-bearing: it tells
Infrahub what MIME type to serve, so a Python
transform that returns a `dict` paired with
`text/plain` writes a stringified Python dict into
the artifact body (not JSON), and consumers that
parse by MIME type get garbage. `targets` is the
group whose members the artifact is materialised for,
and `parameters` maps each target's attributes onto
the named query variables — a missing parameter
silently passes `None` into the query.

### Configuration

```yaml
artifact_definitions:
  - name: spine_config                   # Unique identifier
    artifact_name: spine                 # Display name
    content_type: text/plain             # MIME type
    targets: spines                      # Target group
    transformation: spine                # Transform name (must match)
    parameters:
      device: name__value               # Maps target attribute to query variable
```

### Content Types

The full allowlist is fixed at eight values
(defined as a Python enum in
`infrahub/core/constants/__init__.py` and enforced
on the schema attribute):

| Content Type       | Use Case                             |
| ------------------ | ------------------------------------ |
| `text/plain`       | Device configs, scripts              |
| `text/csv`         | Cable matrices, inventory reports    |
| `text/markdown`    | Generated documentation, reports     |
| `application/json` | Structured data, API payloads        |
| `application/yaml` | YAML config files                    |
| `application/xml`  | XML config / SOAP payloads           |
| `application/hcl`  | Terraform / HCL config               |
| `image/svg+xml`    | Generated diagrams (topology, racks) |

> **Use `application/yaml`, not `text/yaml`.** The
> server validates `content_type` against the
> enum above and rejects anything outside it at
> sync time with `{value} must be one of {schema.enum!r}`.
> A typo here doesn't fail one artifact — every
> `artifact_definitions` entry using it fails on
> first sync.

### Target Requirements

Target nodes inherit from `CoreArtifactTarget` on
the **concrete node**, declared in that node's
source schema file. `extensions:` cannot add
`inherit_from` — see
[../../infrahub-managing-schemas/rules/extension-artifact-target.md](../../infrahub-managing-schemas/rules/extension-artifact-target.md).

```yaml
# In the node's source schema file
nodes:
  - name: Device
    namespace: Dcim
    inherit_from:
      - CoreArtifactTarget            # Required for artifact generation
      - DcimGenericDevice
```

### Key Rules

- `transformation:` resolves by exact-name match
  against `python_transforms` or `jinja2_transforms`;
  a mismatch fails at artifact-render time
- `targets:` is the group whose members the artifact
  is materialised for
- `parameters:` maps target object attributes onto
  named query variables (missing keys pass `None`)
- `content_type:` must match the transform's actual
  output shape, since it drives the served MIME type

Reference:
[infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
