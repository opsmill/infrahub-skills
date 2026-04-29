---
title: Branch-Agnostic Nodes and Attributes
impact: MEDIUM
tags: attribute, branch, branch-agnostic, branch-aware
---

## Branch-Agnostic Nodes and Attributes

Impact: MEDIUM

Infrahub is branch-aware by default: every change to
an object lives on a branch and merges into main with
the proposed-change pipeline. The `branch:` setting
opts a node or attribute out of that workflow. Two
values exist:

| Value | Behavior |
| ----- | -------- |
| `aware` (default) | Changes are scoped to a branch and only become global on merge |
| `agnostic` | Changes apply globally and are not subject to branching |

`branch: agnostic` is rare and load-bearing — use it
deliberately, only for data that *must* be globally
consistent across all branches.

### When to Use `branch: agnostic`

Real-world examples from production schemas:

- **Globally unique business keys** — service names,
  customer identifiers, AS numbers. Branching them
  would let two branches both claim the same key.
- **Read-only reference data** — provider catalogs,
  hardware part numbers from an external system of
  record.
- **Top-level identity fields** that are mirrored
  from external systems and must not diverge across
  branches.

### Node-Level vs Attribute-Level

`branch:` can be set at the node level (every
attribute and relationship inherits it) or scoped to
a single attribute or relationship.

**Node-level:**

```yaml
- name: AutonomousSystem
  namespace: Routing
  branch: agnostic              # Whole node is global
  label: Autonomous System
  uniqueness_constraints:
    - [asn__value]
  attributes:
    - name: asn
      kind: Number
    - name: name
      kind: Text
```

**Attribute-level:**

```yaml
- name: Service
  namespace: Service
  attributes:
    - name: name
      kind: Text
      optional: false
      branch: agnostic          # Service name is global
    - name: status
      kind: Dropdown            # Status remains branch-aware
      choices:
        - name: active
        - name: planned
```

The attribute-level form is the more common pattern:
keep the identity field global, let everything else
branch normally. This is the "namespaces are global,
content branches" model.

### Why It Matters for Uniqueness

If two branches each create an object with the same
key on a `branch: aware` attribute, they coexist
until merge — and then collide. Marking the identity
attribute `branch: agnostic` causes the conflict to
surface at write time on the second branch instead
of at merge time, which is usually what you want for
business identifiers.

### Antipatterns

**Marking everything agnostic to "avoid merge
conflicts":** this defeats branching. The whole
point of branch-aware data is reviewable, isolated
changes. Use `branch: agnostic` only when global
consistency is a hard requirement.

**Mixing agnostic identity with aware relationships
that point at the same object across branches:** the
identity is shared but the relationships diverge,
producing inconsistent views per branch. Decide at
node-design time whether the relationship targets
make sense as branch-aware or should be agnostic
together with the identity.

Reference:
[Infrahub Schema Docs](https://docs.infrahub.app)
