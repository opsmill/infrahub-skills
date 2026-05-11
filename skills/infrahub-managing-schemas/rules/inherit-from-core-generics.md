---
title: Inherit from Core Generics for Downstream Consumers
impact: HIGH
tags: inheritance, CoreArtifactTarget, CoreNode, downstream, artifacts
---

## Inherit from Core Generics for Downstream Consumers

**Impact:** *HIGH*

A schema node that will be consumed by an artifact, generator, or
other Infrahub feature must inherit from the corresponding Core
generic. The inheritance is declared in the schema, but the
*requirement* comes from the downstream feature's contract.

When designing a node, decide upfront how it will be used and add
the right Core generic(s) to `inherit_from`.

| Downstream use | Required inheritance | Owner skill |
| -------------- | -------------------- | ----------- |
| Artifact target (group member referenced by an `artifact_definition`) | `CoreArtifactTarget` | `infrahub-managing-transforms` |
| Generator target (group member referenced by a `generator_definition`) | `CoreArtifactTarget` | `infrahub-managing-generators` |
| Resource pool peer (e.g. IPAM allocation) | feature-specific generic | feature-owning skill |

Core generics commonly mixed in via `inherit_from`:

| Generic | Purpose |
| ------- | ------- |
| `CoreArtifactTarget` | Node instances become artifact targets |
| `CoreNode` | Base node identity (usually implicit) |
| `LineageOwner` / `LineageSource` | Tracks ownership of attribute values |

**Incorrect** -- artifact target without `CoreArtifactTarget`:

```yaml
nodes:
  - name: Server
    namespace: Compute
    attributes:
      - {name: name, kind: Text, unique: true}
# Then in .infrahub.yml:
#   artifact_definitions:
#     - targets: "All Servers"   # group of Compute/Server -- will fail
#       transformation: server_config_transform
```

**Correct** -- declare the contract on the schema node:

```yaml
nodes:
  - name: Server
    namespace: Compute
    inherit_from: ["CoreArtifactTarget"]   # required for artifact generation
    attributes:
      - {name: name, kind: Text, unique: true}
```

Multi-inheritance is fine — combine a domain generic with a Core
generic:

```yaml
nodes:
  - name: InstanceGcp
    namespace: Compute
    inherit_from: ["ComputeInstance", "CoreArtifactTarget"]
```

### Decision rule

Before finalizing any node, ask: *"Will instances of this node ever
appear as members of a group used as `targets:` of an
`artifact_definition` or `generator_definition`?"*  If yes,
`CoreArtifactTarget` belongs in `inherit_from`. Adding it later
forces a schema migration; adding it upfront costs nothing.

### Cross-skill reference

This rule is the schema-side of the contract enforced by
[infrahub-managing-transforms/rules/artifacts-definitions.md](../../infrahub-managing-transforms/rules/artifacts-definitions.md)
and is checked statically by
[infrahub-auditing-repo/rules/artifact-target-inheritance.md](../../infrahub-auditing-repo/rules/artifact-target-inheritance.md).

Reference: [Infrahub Schema Docs](https://docs.infrahub.app/topics/schema/)
