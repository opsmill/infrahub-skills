---
title: Object Templates (generate_template)
impact: MEDIUM
tags: extension, object-template, generate_template, clone, ux
---

## Object Templates (generate_template)

Impact: MEDIUM

`generate_template: true` is a node-level flag that makes
Infrahub generate a `Template<Kind>` node. A template is a
reusable **structure** users clone to create new objects — the
node *and its `Component` children*. For the full mechanics see
[../infrahub-common/profiles-and-templates.md](../../infrahub-common/profiles-and-templates.md).

### Why it matters

When users repeatedly create objects of the same shape — a
device model with a fixed set of interfaces, a topology
blueprint — a template turns "rebuild every child by hand" into
"clone a known-good example." Enabling template generation on a
node automatically brings its `Component` relationships into
the template, so the children come along with the clone.

Set it on concrete nodes whose creation flow benefits from
duplicating a curated instance. It is independent of Profiles
(which move *values*, not structure) and of generators (which
*compute* objects) — enable each on its own merits.

### What a template covers

- **The node's attribute values**, as a starting point (an
  instance can then diverge).
- **`Component` children** — covered automatically when
  template generation is enabled. Each child kind gets its own
  template too (e.g. interface templates under a device
  template), and creating an object from the parent template
  recreates those children on the new object.
- **Group propagation** — `member_of_groups_for_instances` and
  `subscriber_of_groups_for_instances` on the template push
  group membership to *every* object created from it. (Plain
  `member_of_groups` / `subscriber_of_groups` apply to the
  template object itself only.)

Objects are created from a template via the `object_template`
relationship — see
[managing-objects: object templates](../../infrahub-managing-objects/rules/value-profiles-templates.md).

### The pattern

```yaml
- name: Device
  namespace: Dcim
  label: Network Device
  generate_template: true          # enable Template<Kind> generation
  inherit_from:
    - DcimGenericDevice
  attributes:
    - name: name
      kind: Text
      unique: true
    - name: description
      kind: Text
      optional: true
```

A typical workflow: create one template per model
(`arista-7280r-template`, `cisco-9300-template`) capturing that
model's interfaces and defaults, then clone the closest match
when onboarding a new device.

### When to use it

- **Devices per manufacturer/model** — one template per
  platform capturing model-specific children (interface counts,
  slots).
- **Network designs / topology blueprints** cloned per site.
- **Service definitions** with many child parts.
- **Reusable configurations** (route maps, policies) where a
  curated example is the norm.

### When NOT to use it

- **Auto-managed records** owned by a generator or upstream
  sync. Cloning a record the system overwrites just creates
  conflicts and drift.
- **Singletons** — nodes you only ever have one of.
- **Pure reference catalogs** where each row is unique data
  with no "starter" semantic.

### Antipatterns

**On generics:** generics are not instantiable, so template
generation is meaningless. Apply the flag to concrete nodes.

**On generator-managed nodes:** if a generator owns the
lifecycle, templated human copies drift from the source of
truth.

**Confusing it with Profiles:** a template clones *structure*
once; a Profile supplies *live shared values*. Using a template
to push values everyone shares means editing every clone when
the value changes — that is a Profile's job. See
[extension-object-profile.md](./extension-object-profile.md).

### Independent of artifact targets

`generate_template: true` and
`inherit_from: CoreArtifactTarget` solve different problems and
are independent — see
[extension-artifact-target.md](./extension-artifact-target.md).
A node may have both, either, or neither. Pick each based on
actual need, not habit.

Reference: [Infrahub Object Templates docs](https://docs.infrahub.app/object-templates/overview).
