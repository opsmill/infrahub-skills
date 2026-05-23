---
title: One Generator, One Layer
impact: CRITICAL
applies_when: building a modular cascade
tags: cascade, architecture, modular, one-layer
---

## One Generator, One Layer

Impact: CRITICAL (when building a cascade)

Each generator in a cascade owns exactly one hierarchy level. A generator
that creates devices should not also create interfaces; a generator that
allocates IPs should not also create devices. Each layer gets its own
generator file, its own GraphQL query, and its own registration.

### Why It Matters

The cardinal architectural principle of modular generators. Embedding
multiple layers in one generator breaks the cascade's primary benefits:

- **Loss of parallelism** — Infrahub triggers downstream generators only
  after their upstream completes. A monolithic generator can't be split
  across the trigger boundary.
- **Re-run cost** — re-running the upstream forces re-running everything
  bundled with it, even when only the upstream's input changed.
- **Day-two scope creep** — when a new layer needs adding, you either
  bolt it onto the existing generator (compounding the problem) or
  carve it out (rewriting both halves). Neither is cheap.

### The Rule

Inside a single generator class, every `self.client.create(kind=...)`
call should target the same `kind`. If you find yourself creating two
distinct kinds, split into two generators.

This rule applies only when you've decided to build a modular cascade.
A single-generator solution may legitimately create multiple kinds if
the work doesn't split at a meaningful boundary — see
[../SKILL.md](../SKILL.md) Step 2 for that decision.

### Example

**Incorrect — one generator, two layers:**

```python
class DcGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        # Layer 1: create devices
        for element in sorted(elements, key=...):
            device = await self.client.create(kind="DcimDevice", data={...})
            await device.save(allow_upsert=True)

            # Layer 2: create interfaces for each device
            for iface_spec in element["interfaces"]:
                iface = await self.client.create(
                    kind="DcimInterface", data={...},
                )
                await iface.save(allow_upsert=True)
```

**Correct — split into two generators, one per layer:**

```python
# generators/generate_devices.py
class DeviceGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        for element in sorted(elements, key=...):
            device = await self.client.create(kind="DcimDevice", data={...})
            await device.save(allow_upsert=True)


# generators/generate_interfaces.py — triggered by DcimDevice changes
class InterfaceGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        for iface_spec in sorted(iface_specs, key=...):
            iface = await self.client.create(kind="DcimInterface", data={...})
            await iface.save(allow_upsert=True)
```

### Common Mistakes

- Creating "child" objects in the same generator as the parent because
  "they always go together" — they don't, after the first re-run.
- Treating tags or status objects as separate layers — small utility
  attributes attached to the same primary object are fine; what counts
  is whether they would meaningfully re-trigger independently.
- Inlining the downstream layer "for now" with a TODO to split later —
  the split is harder once consumers depend on both layers being in one
  pass.
