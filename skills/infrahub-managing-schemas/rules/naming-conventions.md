---
title: Naming Conventions and Kind Derivation
impact: CRITICAL
tags: naming, namespace, node, attribute, kind
---

## Naming Conventions and Kind Derivation

Impact: CRITICAL

Namespaces, node names, and attribute names follow
fixed regex patterns with hard length limits.

### Why it matters

The Infrahub JSON schema enforces these patterns with
`additionalProperties: false` and explicit regex
checks; `infrahubctl schema check` fails before the
file ever reaches the server. The length minimums
trip up the obvious shorthand — `id` (too short),
`DC` (too short), `MyAttribute` (mixed case) — and
the kind reference everywhere else in the schema is
built from `Namespace + Name`, so a non-conforming
name silently breaks every `peer`, `inherit_from`,
`parent`, and `children` reference that points to it.

### Namespace

Pattern: `^[A-Z][a-z0-9]+$` (first letter uppercase,
rest lowercase letters or digits). Min 3, max 32 chars.

**Incorrect:**

```yaml
namespace: DCIM          # All uppercase
namespace: dcim          # No uppercase
namespace: DC            # Too short (min 3)
```

**Correct:**

```yaml
namespace: Dcim
namespace: Location
namespace: Organization
namespace: Ipam
```

### Node and Generic Names

Pattern: `^[A-Z][a-zA-Z0-9]+$` (PascalCase). Min 2, max 32 chars.

**Incorrect:**

```yaml
name: my_node            # snake_case
name: X                  # Too short
```

**Correct:**

```yaml
name: DeviceType
name: GenericDevice
name: ModuleBayTemplate
```

### Attribute and Relationship Names

Pattern: `^[a-z0-9_]+$` (snake_case). Min 3, max 64 chars.

**Incorrect:**

```yaml
- name: id               # Too short (min 3 chars)
- name: MyAttribute      # Mixed case — needs snake_case
```

**Correct:**

```yaml
- name: obj_id           # Use obj_id instead of id
- name: my_attribute
- name: rack_u_position
```

### Kind Derivation

Kind = Namespace + Name. This is how you reference nodes everywhere.

```text
Dcim + DeviceType = DcimDeviceType
Location + Rack = LocationRack
Organization + Manufacturer = OrganizationManufacturer
```

Use the full kind when referencing in `inherit_from`, `peer`, `parent`, `children`.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
