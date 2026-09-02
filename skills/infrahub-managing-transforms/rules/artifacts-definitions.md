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

**This table is the authority, not the examples.**
All eight values are supported, whether or not a
worked example happens to use them, so read this table
instead of pattern-matching the examples.
`image/svg+xml` is the one most often assumed
unsupported, because it is the only value whose output
is a picture. It is supported, and it is the one whose
payload readers most often assume must be a dict of
geometry. It must not be: like the other five string
types it is serialised with `str()`. For a diagram
artifact end to end, see [../examples.md](../examples.md).

> **Use `application/yaml`, not `text/yaml`.** The
> server validates `content_type` against the
> enum above and rejects anything outside it at
> sync time with `{value} must be one of {schema.enum!r}`.
> A typo here doesn't fail one artifact — every
> `artifact_definitions` entry using it fails on
> first sync.

### What the Content Type Does to Your Return Value

`content_type` is not only a served MIME type. It
selects how the transform's return value is
serialised, and the rule is narrower than it looks:

| Returned | With `application/json` | With `application/yaml` | With any other type |
| -------- | ----------------------- | ----------------------- | ------------------- |
| `dict` | serialised as JSON | serialised as YAML | **`str(dict)`** — a Python repr, silently |
| `str` | stored as-is | stored as-is | stored as-is |
| `None` | error | error | error |

**Only `application/json` and `application/yaml`
special-case a dictionary.** Every one of the other
six passes the payload through `str()`, so returning a
`dict` for `text/csv` or `image/svg+xml` writes
`{'a': 1}` into the artifact body with no error and no
warning. That is the failure worth remembering: it is
silent, and the artifact looks populated.

Returning nothing at all is the one case that does
fail loudly:

```text
The transform at <location> did not return a payload
```

So for the six string types — including
`image/svg+xml` — **the transform must return a
string.** Build the markup or the text yourself and
return it.

Related:
[../reference.md](../reference.md) summarises which
content types suit each return type; this rule is the
authority on how the payload is serialised.

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
