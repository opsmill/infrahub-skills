---
title: Object Templates (generate_template)
impact: MEDIUM
tags: extension, object-template, generate_template, clone, ux
---

## Object Templates (generate_template)

Impact: MEDIUM

`generate_template: true` enables Infrahub's Object
Template UX on a node: users can mark instances as
templates and clone them as starters for new
instances. It is a **node-level capability flag**,
unrelated to artifact rendering or any inheritance
requirement.

Set it on nodes whose creation flow benefits from
duplicating a known-good instance — common patterns,
reusable designs, or "golden" examples that should
be copied rather than re-entered field by field.

### The Pattern

```yaml
- name: Device
  namespace: Dcim
  label: Network Device
  generate_template: true        # Enable clone-from-template UX
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

That single property is the entire feature. No
companion flag is required.

A typical operator workflow on top of this: create
one Device instance per model
(`arista-7280r-template`, `cisco-9300-template`),
mark each as a template in the UI, and have new
device onboarding clone the closest match.

### When to Use It

Anywhere users repeatedly create similar instances
and would benefit from starting from a curated
example rather than filling every field by hand.
Common cases:

- **Devices per manufacturer/model** — a template
  per platform (Arista 7280R, Cisco 9300, Juniper
  QFX5120) capturing the model-specific defaults
  (interface counts, slots, capabilities).
- **Network designs and topology blueprints** users
  duplicate per site/customer.
- **Service definitions** with many fields where
  most new instances start from an existing one.
- **Reusable configurations** (route maps, policies,
  prefix lists) where a curated example is the norm.

The template UX scales linearly with how often users
create instances of similar shape. If "create
another one like that" is a frequent operation,
turn it on.

### When NOT to Use It

- **Auto-managed records** populated by generators
  or upstream sync (computed-only objects, pulled
  inventory). Cloning a record that the system
  overwrites just creates conflicts.
- **Singletons** — nodes you only ever expect to
  have one instance of. The clone UX adds noise for
  a feature that won't be used.
- **Pure reference catalogs** where each row is
  unique data and there is no "starter" semantic
  (e.g., country codes, ASN registry rows pulled
  from external).

When in doubt, prefer enabling it: a template that
goes unused is invisible cost, but a missing
template is a daily papercut for users.

### Independent of Artifact Targets

`generate_template: true` and
`inherit_from: CoreArtifactTarget` solve different
problems and are independent — see
[extension-artifact-target.md](./extension-artifact-target.md).
A node may have:

- Both (a Device that is cloneable *and* produces
  rendered configs)
- Only `generate_template` (a Topology Design that
  is cloneable but has no rendered output)
- Only `CoreArtifactTarget` (a Device that produces
  configs but should not be cloned)
- Neither (the default for most operational records)

Pick each based on the actual need. Adding one
because the other is present is a habit, not a
design decision.

### Antipatterns

**Setting `generate_template: true` on generics:**
generics are not instantiable, so the clone UX is
meaningless. Apply the flag to concrete nodes that
users actually create.

**Setting it on auto-populated nodes:** if a
generator or sync job owns the node's lifecycle,
templates create human-edited copies that drift
from the source of truth. Either disable the
generator on cloned instances or skip templates on
managed records.

**Coupling it to `CoreArtifactTarget` by habit:**
the two flags solve different problems. Adding
`generate_template: true` because a node already
has `CoreArtifactTarget` (or vice versa) is a
mental shortcut, not a design decision — pick each
based on actual need.

Reference:
[Infrahub Schema Docs](https://docs.infrahub.app)
