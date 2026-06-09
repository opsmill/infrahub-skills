# Object File Validation & Loading Guide

> **Server Required**: `infrahubctl object validate`
> and `infrahubctl object load` both require a running
> Infrahub server. Run `infrahubctl info` first to
> verify connectivity. See
> [Server Connectivity Check](../infrahub-common/rules/connectivity-server-check.md).

## Validation Commands

### Validate Object Files (Dry Run)

Validate object YAML files without loading them:

```bash
# Validate a single file
infrahubctl object validate objects/devices.yml

# Validate a whole directory
infrahubctl object validate objects/

# Validate against a specific branch (resolves references against that branch's schema)
infrahubctl object validate objects/ --branch develop
```

This checks:

1. YAML syntax is parseable
2. The envelope is correct (`apiVersion`, `kind: Object`, `spec.kind`, `spec.data`)
3. `spec.kind` exists in the loaded schema
4. Each attribute name maps to a real attribute on that kind
5. Relationship references resolve against the target node's `human_friendly_id` shape

It does **not** actually load anything — useful for
catching shape errors before a `load` writes to the
branch.

### Load Object Files

```bash
# Load everything in objects/
infrahubctl object load objects/

# Load specific files
infrahubctl object load objects/01_manufacturers.yml objects/02_device_types.yml

# Load onto a specific branch (recommended for first loads)
infrahubctl object load objects/ --branch test-load

# Verbose mode — show each object as it loads
infrahubctl object load objects/ --debug
```

Loads are not transactional across files: if file
17 fails partway through, files 1-16 are already
written. Test on a branch (`--branch test-load`)
before loading to the default branch.

### What `object load` Does NOT Load

`infrahubctl object load` ingests only object YAML
files (`apiVersion: infrahub.app/v1`, `kind: Object`).
It does **not** read `.infrahub.yml` and does **not**
ingest the `queries:`, `python_transforms:`,
`jinja2_transforms:`, `check_definitions:`,
`generator_definitions:`, or `artifact_definitions:`
sections. Those are repo-lifecycle objects, picked
up only when the repository itself is registered as
a `CoreReadOnlyRepository` (or `CoreRepository`) and
the worker pulls from git. See
[../infrahub-managing-transforms/rules/testing-commands.md](../infrahub-managing-transforms/rules/testing-commands.md)
for the lifecycle split.

## Common Load Errors

### "kind not found in the schema"

`spec.kind` doesn't exist on the target branch:

```yaml
spec:
  kind: DcimDellServer            # Not in schema → rejected
```

The schema must already include the kind. Schema is
loaded before objects (`infrahubctl schema load`
first, then `infrahubctl object load`).

### "Attribute X is not a valid attribute"

Trying to set an attribute that doesn't exist on the
kind:

```yaml
spec:
  kind: DcimInterface
  data:
    - name: eth0
      enabled: true                # Not on this schema's Interface
```

Introspect the schema before setting attributes —
field sets vary by deployment. See
[../infrahub-common/netbox-vs-infrahub.md](../infrahub-common/netbox-vs-infrahub.md)
for the introspection commands.

### "Invalid structure for a relationship of cardinality many"

A cardinality-many relationship was given the wrong
shape. The correct shapes are either a list of HFID
references or a `data:`-wrapped object:

```yaml
# OK — list of HFIDs (member-side, for group membership)
member_of_groups:
  - leafs
  - cisco_leaf

# OK — data-wrapped (component-children style)
interfaces:
  data:
    - name: eth0
    - name: eth1

# WRONG — bare list under a non-many relationship
device:
  - kind: DcimDevice                # device is cardinality one — reject
```

See
[rules/value-relationships.md](./rules/value-relationships.md)
for HFID-shape rules and
[rules/children-components.md](./rules/children-components.md)
for component-child structure.

### "Reference not found"

Cross-file reference to an object that hasn't loaded
yet. Load order matters because references resolve
at insert time — an object referencing one that
hasn't loaded fails the whole batch.

Fix by numbering files for explicit load order:

```text
objects/
  01_manufacturers.yml         # Depends on nothing
  02_device_types.yml          # References manufacturers
  03_locations.yml             # Depends on nothing
  10_devices.yml               # References device_types and locations
```

See [rules/organization-load-order.md](./rules/organization-load-order.md).

### "expand_range is not a valid attribute"

`expand_range: true` belongs in the `parameters:`
block at the top level of the document, not on
individual `data:` items:

```yaml
spec:
  kind: DcimInterface
  parameters:
    expand_range: true             # Here
  data:
    - name: "eth[0-47]"            # Range syntax expands at load time
      # expand_range: true         # NOT here
```

See [rules/range-expansion.md](./rules/range-expansion.md).

### "Dropdown value not in choices"

Dropdown attributes reference the choice **name**,
not the human-readable label:

```yaml
# Schema declares:
#   choices:
#     - name: active
#       label: "Active"

data:
  - status: active                 # Use the name
  # - status: "Active"             # WRONG — that's the label
```

## Pre-Load Checklist

Before running `infrahubctl object load`, verify:

- [ ] Server is reachable (`infrahubctl info` succeeds)
- [ ] Schema for every `spec.kind` referenced is already loaded on the target branch
- [ ] Every file starts with `apiVersion: infrahub.app/v1` and `kind: Object`
- [ ] `spec.kind` and `spec.data` are present on every document
- [ ] Cross-file references use the target node's `human_friendly_id` shape (scalar for 1-element HFID, list for multi-element)
- [ ] Dropdown values are choice `name`s, not labels
- [ ] File ordering reflects dependencies (numeric `01_`, `02_` prefixes when needed)
- [ ] Component children use `<rel>: { kind, data: [...] }` shape
- [ ] `member_of_groups` is on the member side, not inline `members:` on the group
- [ ] `expand_range: true` is in `parameters:`, not on individual items
- [ ] Bootstrap files are **not** in `objects/` (they'd re-load on every sync, overwriting state)
- [ ] First load goes to a dedicated branch, not the default branch

## Branch-Based Object Loads

The `--branch` flag scopes the load to a specific
branch — useful for staging large changes:

```bash
# Create a branch (via UI or API) then:
infrahubctl object load objects/ --branch staging-q1

# Test, validate, fix
infrahubctl object validate objects/ --branch staging-q1

# Merge via Infrahub UI when ready
```

`branch: agnostic` attributes (like AS numbers,
service names, customer IDs) write the same value
across all branches regardless of which branch the
load targets. See
[../infrahub-managing-schemas/rules/attribute-branch-agnostic.md](../infrahub-managing-schemas/rules/attribute-branch-agnostic.md).

## Related

- [reference.md](./reference.md) — object file format reference
- [examples.md](./examples.md) — 15 worked patterns
- [rules/](./rules/) — detailed structural rules
