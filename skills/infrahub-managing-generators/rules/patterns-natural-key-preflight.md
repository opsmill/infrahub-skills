---
title: Pre-flight Natural-Key Check for Form-Driven Mutations
impact: MEDIUM
tags: patterns, idempotent, uniqueness, upsert, form, catalog
---

## Pre-flight Natural-Key Check for Form-Driven Mutations

Impact: MEDIUM

Inside ``InfrahubGenerator.generate()`` the default ``save()``
already happens with ``allow_upsert=True`` because the tracking
context wraps the call. **Outside that context** — in scripts,
Streamlit pages, or any ad-hoc code that takes user input and
calls ``client.create`` directly — uniqueness collisions on
bootstrap-seeded keys surface as raw server exceptions in the
middle of a half-built workflow.

Always pick one of two patterns for catalog-style mutations.

### Pattern A — pre-flight check

Use when the desired behavior is "fail loudly with a friendly
message if the object already exists."

```python
from infrahub_sdk.exceptions import NodeNotFound

try:
    existing = await client.get(
        kind="IpamPrefix",
        prefix__value=user_input_prefix,
    )
    st.error(f"Prefix {user_input_prefix} already exists.")
    return
except NodeNotFound:
    pass

prefix = await client.create(
    kind="IpamPrefix",
    data={"prefix": user_input_prefix},
)
await prefix.save()
```

### Pattern B — upsert

Use when the desired behavior is "create or update silently."
This is the default inside generators.

```python
prefix = await client.create(
    kind="IpamPrefix",
    data={"prefix": user_input_prefix},
)
await prefix.save(allow_upsert=True)
```

### Anti-pattern

```python
# WRONG — uniqueness collision surfaces as raw server exception
prefix = await client.create(
    kind="IpamPrefix",
    data={"prefix": user_input_prefix},
)
await prefix.save()  # no upsert, no preflight
```

### How to decide

- **Form-driven UI catalog pages:** Pattern A. Give the user a
  legible "already exists" message.
- **Generators with tracking:** ``allow_upsert=True`` is the
  norm — the generator should be idempotent.
- **Bootstrap scripts and migrations:** Pattern B (upsert)
  unless you have a specific reason to fail on existing data.

Reference: [Infrahub SDK Docs](https://docs.infrahub.app)
