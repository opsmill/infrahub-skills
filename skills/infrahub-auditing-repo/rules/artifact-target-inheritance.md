---
title: artifact-target-inheritance
impact: HIGH
tags: audit, schema, artifacts
---

# Rule: artifact-target-inheritance

**Severity**: HIGH
**Category**: Schema integrity

## What It Checks

Every node whose instances can become an artifact or
generator target inherits from `CoreArtifactTarget`,
walking the full `inherit_from` chain through any
intermediate generics.

## Why it matters

Without `CoreArtifactTarget` in the inheritance
chain, the artifact pipeline can't resolve the
target node and either rejects the job with a
"target node does not support artifacts" error or
silently produces nothing — the proposed change
pipeline goes green but no artifact lands in the
object's `artifacts` relationship. The failure is
runtime-only, so the schema loads fine and the
issue surfaces only when someone opens the device
in the UI and finds no rendered config. Catching
this at audit time avoids a debugging detour
through pipeline logs.

## Checks

For each entry in `.infrahub.yml -> artifact_definitions`:

1. Resolve the `targets:` value to a `CoreStandardGroup`
   (or another group kind) — either declared in the
   project's object files, or seeded programmatically
   (e.g. via `src/main.py` or a bootstrap script).
2. Determine the schema kinds permitted as members of
   that group. By convention, the seeding code calls
   `client.all("<Kind>")` or specifies `members=[...]`
   of a single kind; record those kinds.
3. For each candidate kind, walk the inheritance chain
   (`inherit_from` on the node, recursively through any
   parent generics). Assert that `CoreArtifactTarget`
   appears somewhere in the chain.
4. Repeat the same check for `generator_definitions`.

## Common Issues

- New node added that becomes a group member, but the
  schema author forgot the `CoreArtifactTarget` mixin
- Refactor moved the `inherit_from` declaration from a
  leaf node up to a generic, then a sibling node was
  added that inherits from the same generic but bypasses
  the mixin
- Multi-inheritance dropped `CoreArtifactTarget` while
  keeping the domain generic (e.g.
  `inherit_from: ["DomainBase"]` instead of
  `inherit_from: ["DomainBase", "CoreArtifactTarget"]`)

## How to Fix

Add `CoreArtifactTarget` to the `inherit_from` list of
the concrete target node. Apply it to leaf nodes, not
to a shared generic — generics aren't instantiable and
artifacts attach to instances.

```yaml
nodes:
  - name: InstanceGcp
    namespace: Compute
    inherit_from: ["ComputeInstance", "CoreArtifactTarget"]
```

## Related

- Schema-side rule:
  [../../infrahub-managing-schemas/rules/extension-artifact-target.md](../../infrahub-managing-schemas/rules/extension-artifact-target.md)
- Transform-side rule:
  [../../infrahub-managing-transforms/rules/artifacts-definitions.md](../../infrahub-managing-transforms/rules/artifacts-definitions.md)
