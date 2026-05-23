---
title: Naming Conventions and Kind Derivation
impact: CRITICAL
tags: naming, namespace, node, attribute, kind
---

## Naming Conventions and Kind Derivation

Impact: CRITICAL

Infrahub enforces strict naming patterns via JSON schema
validation. Violations cause immediate validation errors.

### Namespace

Pattern: `^[A-Z][a-z0-9]+$` (first letter uppercase,
rest lowercase letters or digits).

**Incorrect:**

```yaml
namespace: DCIM          # All uppercase
namespace: dcim          # No uppercase
```

**Correct:**

```yaml
namespace: Dcim
namespace: Location
namespace: Organization
namespace: Ipam
```

### Node and Generic Names

Pattern: `^[A-Z][a-zA-Z0-9]+$` (PascalCase).

**Incorrect:**

```yaml
name: my_node            # snake_case
```

**Correct:**

```yaml
name: DeviceType
name: GenericDevice
name: ModuleBayTemplate
```

### Attribute and Relationship Names

Pattern: `^[a-z0-9_]+$` (snake_case).

**Incorrect:**

```yaml
- name: MyAttribute      # Must be lowercase
```

**Correct:**

```yaml
- name: obj_id
- name: my_attribute
- name: rack_u_position
```

The regex patterns above are stable across Infrahub
versions and enforced at both `schema check`
(JSON-Schema lint) and `schema load` (server
Pydantic). **Length caps are version-dependent and
must be resolved from the running instance's
OpenAPI spec, not hardcoded here.** See
[validation-string-limits](./validation-string-limits.md)
for the lookup procedure
(`INFRAHUB_ADDRESS` → `localhost:8000` fallback →
`/api/openapi.json`) and for the `label`,
`description`, `identifier`, and `deprecation` caps
that the JSON-Schema lint silently passes over.

### Kind Derivation

Kind = Namespace + Name. This is how you reference nodes everywhere.

```text
Dcim + DeviceType = DcimDeviceType
Location + Rack = LocationRack
Organization + Manufacturer = OrganizationManufacturer
```

Use the full kind when referencing in `inherit_from`, `peer`, `parent`, `children`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
