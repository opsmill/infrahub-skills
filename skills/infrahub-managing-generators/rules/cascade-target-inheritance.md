---
title: Downstream Nodes Inherit GeneratorTarget
impact: CRITICAL
applies_when: building a modular cascade
tags: cascade, schema, GeneratorTarget, inheritance, checksum
---

## Downstream Nodes Inherit GeneratorTarget

Impact: CRITICAL (when building a cascade)

Any node kind that participates in a cascade as a downstream target must
inherit from a `GeneratorTarget` generic. The generic provides the
`checksum` attribute that the cascade uses to decide whether to re-trigger
downstream work.

### Why It Matters

The cascade pattern needs a place to record "what state did this object
last reach?" so subsequent runs can compare against it. The
`GeneratorTarget` generic supplies that storage as a schema-level
`checksum` attribute on every downstream node.

Without inheriting `GeneratorTarget`:

- Downstream nodes have nowhere to write their checksum.
- Every re-run of the upstream forces every downstream generator to do
  the full work — there's no way to skip identical-input runs.
- The cascade exists in name only; in practice it re-cascades every
  time.

### The Rule

In the schema YAML for any node kind that acts as the downstream target
of a generator, include `GeneratorTarget` (or the equivalent built-in
generic kind such as `BuiltinGeneratorTarget`) in `inherit_from`.

This rule applies only to nodes that downstream generators consume. A
schema for a flat single-generator design does not need `GeneratorTarget`.

### Example

**Incorrect — downstream device has no checksum storage:**

```yaml
nodes:
  - name: Device
    namespace: Dcim
    attributes:
      - name: name
        kind: Text
    relationships:
      - name: interfaces
        peer: DcimInterface
        kind: Component
```

**Correct — downstream node inherits GeneratorTarget:**

```yaml
nodes:
  - name: Device
    namespace: Dcim
    inherit_from:
      - GeneratorTarget
    attributes:
      - name: name
        kind: Text
    relationships:
      - name: interfaces
        peer: DcimInterface
        kind: Component
```

The `checksum` attribute is now available on every `DcimDevice` instance
without you defining it explicitly.

### Common Mistakes

- Defining a custom `checksum` attribute on the node instead of
  inheriting from `GeneratorTarget` — works, but bypasses the cascade's
  trigger machinery that recognizes `GeneratorTarget` descendants.
- Adding `GeneratorTarget` to the upstream node (the design object) by
  mistake — the inheritance belongs on whatever the *downstream*
  generator creates or modifies, not on its trigger.
- Forgetting `GeneratorTarget` on intermediate layers — if your cascade
  is A → B → C, both B and C need the inheritance.
