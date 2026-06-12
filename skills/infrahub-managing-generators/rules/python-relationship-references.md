---
title: Passing Relationships to client.create
impact: CRITICAL
tags: python, client, create, hfid, relationship, id
---

## Passing Relationships to client.create

Impact: CRITICAL

The SDK accepts four explicit forms for relationship fields in
the ``data=`` dict of ``client.create()``. Mixing them up — or
passing a bare string — is the most common source of "Unable to
find the node" errors at runtime.

### The three accepted forms

**Form A — HFID lookup (single-component).** Use when the target
schema's ``human_friendly_id`` is one field. The list contains
exactly one string.

```python
await self.client.create(
    kind="DcimDevice",
    data={
        "name": "cEdge-1",
        "device_type": {"hfid": ["cEdge-1000"]},
        "platform": {"hfid": ["ios-xe"]},
    },
)
```

**Form B — HFID lookup (composite).** Use when
``human_friendly_id`` has multiple components. The list order
**must** match the schema's declared order.

```python
# Schema: DcimInterface.human_friendly_id = [device__name__value, name__value]
await self.client.create(
    kind="DcimInterface",
    data={
        "name": "Ethernet1/1",
        "device": {"hfid": ["spine-01"]},
        "connected_to": {"hfid": ["leaf-01", "Ethernet2/2"]},
    },
)
```

**Form C — Explicit ID.** Use when you already hold the UUID
(returned by a prior query).

```python
await self.client.create(
    kind="DcimDevice",
    data={
        "name": "cEdge-1",
        "site": {"id": site_uuid},
    },
)
```

**Form D — SDK object reference (passed directly).** Pass an
object previously returned by ``self.client.get`` or
``self.client.create``.

```python
site = await self.client.get(kind="LocationSite", name__value="PAR-1")
await self.client.create(
    kind="DcimDevice",
    data={
        "name": "cEdge-1",
        "site": site,
    },
)
```

### Anti-pattern: bare string

A bare string for a relationship field is interpreted as
``{"id": "<string>"}``. The server then tries to look up the
string as a UUID, fails, and returns "Unable to find the node".

```python
# WRONG — server returns "Unable to find the node cEdge-1000 / DcimDeviceType"
await self.client.create(
    kind="DcimDevice",
    data={
        "name": "cEdge-1",
        "device_type": "cEdge-1000",  # treated as id, not HFID
    },
)
```

### Anti-pattern: over-packed HFID list

The HFID list length **must match** the schema's
``human_friendly_id`` declaration. Padding a single-component
HFID with extra fields causes the lookup to fail.

```python
# WRONG — DcimDeviceType.human_friendly_id is [name__value], single-component.
# Adding manufacturer to the list breaks the lookup.
await self.client.create(
    kind="DcimDevice",
    data={
        "device_type": {"hfid": ["cEdge-1000", "Cisco"]},  # over-packed
    },
)
```

### How to know which form to use

1. Find the target relationship's ``peer:`` kind in the schema.
2. Look up that node's ``human_friendly_id:`` list. The length
   tells you how many strings go in the ``hfid`` list.
3. If you already hold a UUID, use ``{"id": ...}``. Otherwise
   prefer ``{"hfid": [...]}``.
4. If you have an SDK object in scope (from ``client.get`` or
   ``client.create``), pass it directly — Form D.

The same forms apply to **every** relationship in the generator,
not only the examples above. If a relationship field doesn't fit
forms A-D, it is shape-wrong — fix it.

Reference: [Infrahub Generator Docs](https://docs.infrahub.app)
