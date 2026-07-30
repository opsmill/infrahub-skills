---
title: Adopt Generated Protocols for Typed Schema Access
impact: LOW
tags: protocols, infrahubctl, type-safety, generators, transforms, checks
---

## Adopt Generated Protocols for Typed Schema Access

When Python — a generator, transform, or check — reads or writes schema
objects through the SDK, pass a generated protocol class as the `kind` instead
of a string. You get dev-time type checking and IDE autocomplete on the
object's attributes, and a later schema change becomes a type error on the
exact line rather than a runtime failure.

### Generate the protocols

`infrahubctl protocols` writes a Python module of typed classes for your
schema. The async client is the default; add `--sync` for the sync client.

```bash
# From a running instance (async client)
export INFRAHUB_ADDRESS=https://infrahub.example.com
infrahubctl protocols --out lib/protocols.py

# From local schema files, no instance needed
infrahubctl protocols --schemas schemas/ --out lib/protocols.py

# Sync client
infrahubctl protocols --schemas schemas/ --sync --out lib/protocols.py
```

### Use them

```python
from lib.protocols import NetworkDevice   # or a protocols.py beside the script

device = await client.create(NetworkDevice, hostname="spine-1", role="spine")
device.hostname.value            # type-checked and autocompleted
```

For core and internal kinds you generate nothing — import them straight from
the SDK: `from infrahub_sdk.protocols import CoreIPPrefixPool`.

### Caveats

- **Attributes only.** Relationships are `RelatedNode` / `RelationshipManager`
  with no peer type; re-`get(Peer, ...)` when you need typed peer access.
- **Regenerate after any schema change** and commit the file — it does not
  update itself, and a stale file gives wrong types silently.
- **Match sync vs async to your client** — a sync check imports the `--sync`
  variant; async uses the default.
- Local-directory generation does not emit Profile or Object-Template
  protocols.

See [protocols-generated](./protocols-generated.md) for why the file is a
build artifact you never hand-edit. The auditor flags untyped string kinds via
[yagni-untyped-python-vs-generated-protocols](../../infrahub-auditing-repo/rules/yagni-untyped-python-vs-generated-protocols.md).
