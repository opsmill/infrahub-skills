---
title: Assigning Profiles and Object Templates
impact: MEDIUM
tags: value, relationship, profile, object-template
---

## Assigning Profiles and Object Templates

Impact: MEDIUM

Two schema features surface as relationships you set on an
object in its data YAML. They are different tools — see
[../infrahub-common/profiles-and-templates.md](../../infrahub-common/profiles-and-templates.md)
for which to reach for.

### Assigning Profiles (shared default values)

An object inherits default values — attributes *and*
relationship peers (e.g. a default site) — from one or more
Profiles via a `profiles:` list, each entry a Profile's
`human_friendly_id`. An explicit attribute on the object
overrides the Profile value; unset attributes inherit it.
Overriding a Profile-supplied **relationship** replaces it as a
whole (it clears the Profile-source for every peer in that
relationship).

```yaml
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: leaf-01
      profiles:
        - datacenter-defaults      # inherits mtu, status, timezone
    - name: leaf-02
      profiles:
        - datacenter-defaults
      mtu: 1500                     # explicit value overrides the Profile
```

Load order matters: the Profile instances must exist before
the objects that reference them. Create Profiles in an earlier
document/file (or earlier in load order) than the objects — the
same dependency discipline as any relationship reference (see
[organization-load-order.md](./organization-load-order.md)).

### Creating from an Object Template (cloned structure)

To create an object from a template, set its `object_template`
to the template's `human_friendly_id`. Infrahub copies the
template's values and recreates its component children on the
new object — you only specify what differs (e.g. the serial
number, the name).

```yaml
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: leaf-03
      object_template: template-leaf-switch   # clones structure + children
      serial_number: SN-000123                # per-instance detail
```

### Common mistakes

- **Using `profiles:` to copy structure**, or `object_template`
  to share live values — wrong tool. Profiles move values;
  templates clone structure once.
- **Referencing a Profile/template that loads later** — the
  reference fails to resolve. Order the Profile/template first.
- **Re-stating every Profile value on the object** — defeats
  the point; only set the attributes that must differ.
