---
title: Profiles (generate_profile)
impact: MEDIUM
tags: extension, profile, generate_profile, defaults, ux
---

## Profiles (generate_profile)

Impact: MEDIUM

`generate_profile: true` is a node-level flag that makes
Infrahub generate a companion `Profile<Kind>` node. Profile
instances hold **default values — for attributes and for
relationship peers** — that objects inherit unless they set
them explicitly. For the full mechanics — priority, overrides,
provenance — see
[../infrahub-common/profiles-and-templates.md](../../infrahub-common/profiles-and-templates.md).

### Why it matters

A Profile earns its cost when the same values recur across
many objects and should change in one place. Enabling it turns
"edit 300 devices" into "edit one Profile." But it is a
heavier mechanism than a plain default: it adds a node kind, a
relationship, and priority resolution. Reaching for it when a
single value never varies is over-engineering — an attribute
`default_value` covers that for free (see
[attribute-defaults-and-types.md](./attribute-defaults-and-types.md)).

### The pattern

```yaml
- name: Device
  namespace: Dcim
  generate_profile: true          # enable Profile<Kind> generation
  inherit_from:
    - DcimGenericDevice
  human_friendly_id:
    - hostname__value
  attributes:
    - name: hostname
      kind: Text
      unique: true
    - name: mtu
      kind: Number
      optional: true              # profile-supplied defaults target optional attrs
```

Operators then create Profile instances (e.g. `mtu = 9000` for
a "jumbo-frames" Profile) and assign them to devices. See
[managing-objects: assigning profiles](../../infrahub-managing-objects/rules/value-profiles-templates.md).

### When to use it

- Values shared across many instances that must stay in sync
  (site-tier MTU, default status, standard NTP/timezone).
- Default **relationship peers** shared across instances (a
  default site/location, an untagged VLAN for end-user
  interfaces).
- Sets of related defaults a user picks as a bundle
  ("production" vs "lab" defaults).

### When NOT to use it

- **A single fixed default that never varies** — use the
  attribute's `default_value`. A Profile for one constant value
  is pure overhead.
- **Generics** — not instantiable, so no Profile is generated.
  Apply the flag to concrete nodes.
- **Singletons** — one instance means nothing to keep in sync.

### Constraints

Profiles cannot cover everything — do not point users at them
for values they cannot hold:

- Attributes/relationships that are part of a **uniqueness
  constraint or the HFID** are not supported.
- Only **`Attribute`- and `Generic`-kind relationships** are
  profilable (not `Component`/`Parent`).
- Assignment is **static** — no conditional rules, and a
  Profile **cannot extend another Profile**.
- A `Profile<Kind>` is **node-type-specific** — no cross-schema
  or global Profiles.

### Antipatterns

**`generate_profile: true` on a generic:** meaningless; the
flag belongs on the concrete, instantiable node.

**Using a Profile to clone structure:** Profiles move values,
not related objects. To clone a node *and its children*, use an
Object Template — see
[extension-object-template.md](./extension-object-template.md).

Reference: [Infrahub Profiles docs](https://docs.infrahub.app/profiles/overview).
