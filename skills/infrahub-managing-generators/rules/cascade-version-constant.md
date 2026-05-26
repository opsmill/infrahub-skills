---
title: GENERATOR_VERSION Constant
impact: HIGH
applies_when: building a modular cascade
tags: cascade, version, checksum, re-cascade
---

## GENERATOR_VERSION Constant

Impact: HIGH (when building a cascade)

A cascade generator defines a module-level `GENERATOR_VERSION` string
constant and mixes it into the checksum input. Bumping the constant
forces every downstream node to re-cascade on the next run, even when
input data is unchanged.

### Why It Matters

The checksum guard ([cascade-checksum-guard.md](./cascade-checksum-guard.md))
skips work when input data hasn't changed. But sometimes *the generator's
logic* has changed — a bug fix, a new field, a different naming scheme.
The data is the same; the *meaning* of that data is different.

`GENERATOR_VERSION` is the escape hatch. Bumping it from `"1"` to `"2"`
invalidates every previously-computed checksum, forcing every downstream
node through the full work path exactly once.

Without a version constant, the only way to force a re-cascade is to
mutate every upstream input, which is invasive and may not be possible
on a production branch.

### The Rule

At module scope (top of the generator file), define:

```python
GENERATOR_VERSION = "1"
```

Include `f"v{GENERATOR_VERSION}:"` (or equivalent) as a prefix on the
string you hash to produce the checksum. Increment the constant whenever
logic changes in a way that should propagate to downstream nodes even
without input change.

### Example

**Correct — version prefixed into hash input:**

```python
import hashlib

GENERATOR_VERSION = "1"


class MyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        sorted_ids = ",".join(sorted(d["id"] for d in data["upstream"]))
        new_checksum = hashlib.sha256(
            f"v{GENERATOR_VERSION}:{sorted_ids}".encode()
        ).hexdigest()
        # ... compare against downstream.checksum.value, do work, save ...
```

When you next change the generator's logic in a way that needs to reach
existing downstream state:

```python
GENERATOR_VERSION = "2"  # logic changed — force re-cascade everywhere
```

### Common Mistakes

- Using an integer instead of a string — works, but `f"v{GENERATOR_VERSION}:"`
  becomes `"v2:"` either way; string is conventional.
- Forgetting to include the constant in the hash input — bumping the
  number then has no effect.
- Bumping the version for every change — it's specifically for
  *logic-changes-that-must-reach-existing-state*. Routine refactors
  that don't change output don't need a bump.
- Storing the version in a config file or environment variable — the
  constant should travel with the generator code so version history
  matches behavior history.
