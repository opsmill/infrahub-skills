---
title: Checksum Guard Before Downstream Save
impact: CRITICAL
applies_when: building a modular cascade
tags: cascade, checksum, idempotent, re-trigger
---

## Checksum Guard Before Downstream Save

Impact: CRITICAL (when building a cascade)

A downstream generator must compute a checksum of its inputs, compare it
against the downstream node's stored `checksum.value`, and skip the save
when they match. After doing work, it writes the new checksum to the
downstream node.

### Why It Matters

Without a checksum guard, every upstream re-run forces every downstream
generator to do full work — defeating the cascade's primary purpose.
With the guard:

- Identical inputs across runs → downstream is a no-op.
- Changed inputs → downstream runs, writes new checksum.
- Logic changes (bumping `GENERATOR_VERSION`) → checksums no longer
  match, downstream re-runs everywhere.

The guard is what makes a cascade *modular* rather than just *split*.

### The Rule

Inside `generate()`:

1. Compute a checksum (`hashlib.sha256`, `hashlib.md5`, or similar) over
   the inputs that determine downstream output. Prefix the constant
   `GENERATOR_VERSION` into the hash input (see
   [cascade-version-constant.md](./cascade-version-constant.md)).
2. Read the existing `checksum.value` from the downstream node.
3. If they match, skip the work for that node.
4. Otherwise, do the work, then write the new checksum and save with
   `allow_upsert=True`.

### Example

**Incorrect — re-creates downstream state every run:**

```python
async def generate(self, data: dict) -> None:
    for device in sorted(data["devices"], key=lambda d: d["id"]):
        iface = await self.client.create(
            kind="DcimInterfaceManagement",
            data={"device": device["id"], "name": "mgmt0"},
        )
        await iface.save(allow_upsert=True)
```

**Correct — checksum guards the save:**

```python
import hashlib


GENERATOR_VERSION = "1"


async def generate(self, data: dict) -> None:
    for device in sorted(data["devices"], key=lambda d: d["id"]):
        sorted_ids = ",".join(sorted(d["id"] for d in [device]))
        new_checksum = hashlib.sha256(
            f"v{GENERATOR_VERSION}:{sorted_ids}".encode()
        ).hexdigest()

        existing = await self.client.get(
            kind="DcimDevice", id=device["id"],
        )
        if existing.checksum.value == new_checksum:
            continue  # downstream already in sync

        iface = await self.client.create(
            kind="DcimInterfaceManagement",
            data={"device": device["id"], "name": "mgmt0"},
        )
        await iface.save(allow_upsert=True)

        existing.checksum.value = new_checksum
        await existing.save(allow_upsert=True)
```

### Common Mistakes

- Checking the checksum *after* doing the work — the work has already
  run, and you've gained nothing.
- Forgetting to write the new checksum after the work — next run sees
  the old checksum, re-runs the work, never settles.
- Hashing unstable inputs (sets, dicts in insertion order, raw GraphQL
  responses) — produces different checksums for identical state. Sort
  inputs before hashing.
- Skipping `GENERATOR_VERSION` in the hash input — logic changes can't
  force a re-cascade because old checksums still match.
