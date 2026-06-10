---
title: Artifact Targets (CoreArtifactTarget)
impact: MEDIUM
tags: extension, artifact, CoreArtifactTarget, inheritance
---

## Artifact Targets (CoreArtifactTarget)

Impact: MEDIUM

Concrete nodes that artifact definitions render
against inherit from `CoreArtifactTarget` alongside
their domain generics.

### Why it matters

Artifact pipelines bind by inheritance: an artifact
definition in `.infrahub.yml` declares a `targets:`
group whose members come from a kind that inherits
`CoreArtifactTarget`. Without
the inheritance, the pipeline fails at runtime with
`target kind does not support artifacts` and no
rendered output is produced. The cost of adding the
inheritance later is a schema migration on every
already-loaded instance, where adding it on day one
is free — that asymmetry is why this is a
design-time decision, not a refactor.

This is independent of the Object Template feature
(`generate_template: true`) — see
[extension-object-template.md](./extension-object-template.md).
Use each based on the actual need.

### The Pattern

```yaml
nodes:
  - name: Device
    namespace: Dcim
    label: Network Device
    icon: clarity:network-switch-solid
    inherit_from:
      - CoreArtifactTarget         # Receive rendered configs
      - DcimGenericDevice
      - DcimPhysicalDevice
    uniqueness_constraints:
      - [name__value]
    attributes:
      - name: role
        kind: Dropdown
        choices:
          - name: leaf
          - name: spine
          - name: edge
```

Artifact definitions in `.infrahub.yml` reference a
`targets:` group whose members come from a kind that
inherits `CoreArtifactTarget`. Without the
inheritance, transforms cannot attach to instances
of this node.

### Apply It to the Concrete, Not the Generic

Generics cannot be artifact targets — artifacts
attach to instances. If a domain generic
(`DcimGenericDevice`) is shared by several concrete
node types, add `CoreArtifactTarget` to each
concrete node that should carry artifacts, not to
the shared generic.

```yaml
generics:
  - name: GenericDevice
    namespace: Dcim
    # Do NOT add CoreArtifactTarget here

nodes:
  - name: PhysicalDevice
    namespace: Dcim
    inherit_from:
      - CoreArtifactTarget         # Artifact-bearing concrete
      - DcimGenericDevice

  - name: VirtualDevice
    namespace: Dcim
    inherit_from:
      - CoreArtifactTarget         # Artifact-bearing concrete
      - DcimGenericDevice
```

### Pairing With Display Properties

Multi-generic concrete nodes (a `Device` inheriting
from `CoreArtifactTarget`, `DcimGenericDevice`, and
`DcimPhysicalDevice`) should declare `display_label`
and `human_friendly_id` on the concrete node, since
the multi-generic combination may not match what any
single generic's defaults provide:

```yaml
display_label: hostname__value
human_friendly_id:
  - hostname__value
```

### Decision Rule (Design Time)

Before finalizing any node, ask: *"Will instances of
this node ever appear as members of a group used as
`targets:` of an `artifact_definition` or
`generator_definition`?"* If yes,
`CoreArtifactTarget` belongs in `inherit_from` from
day one. Adding it later forces a schema migration on
already-loaded data; adding it upfront costs nothing.

This rule is the schema-side of the contract enforced
by
[../../infrahub-managing-transforms/rules/artifacts-definitions.md](../../infrahub-managing-transforms/rules/artifacts-definitions.md)
and checked statically by
[../../infrahub-auditing-repo/rules/artifact-target-inheritance.md](../../infrahub-auditing-repo/rules/artifact-target-inheritance.md).

### Antipatterns

**`CoreArtifactTarget` on a generic:** generics are
not instantiable, so artifacts have nothing to
attach to. Symptom at runtime: artifact pipelines
fail with "target kind does not support artifacts."

**`CoreArtifactTarget` on a node that does not
produce artifacts:** the node carries an unused
`artifacts` relationship and shows up as a candidate
in artifact-definition wiring, leading to
mis-targeted definitions in `.infrahub.yml`.

**Forgetting `CoreArtifactTarget` on a node that
artifact definitions point at:** the artifact
pipeline cannot bind. Add the inheritance to the
concrete node, not its generic.

**Trying to add `CoreArtifactTarget` via `extensions:`:**
the `extensions:` block only takes new `attributes:`
and `relationships:` on an existing node — adding
`inherit_from`, `generics:`, or any other top-level
property either raises `ValidationError`
(server-side) or silently drops (SDK-side). The
inheritance is never applied either way. Edit the
node's source schema file instead, or define your
own concrete node that inherits from the foreign
generic plus `CoreArtifactTarget`.

Reference:
[Infrahub Schema Docs](https://docs.infrahub.app)
