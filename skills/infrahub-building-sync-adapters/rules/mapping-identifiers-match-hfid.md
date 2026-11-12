---
title: Make Sync Identifiers Match the Destination Human-Friendly ID
impact: CRITICAL
description: >-
  The identifiers of each schema_mapping entry are the fields of the
  destination kind's human_friendly_id, inherited from a generic when the node
  has none. A different key lets the Infrahub upsert merge records silently.
  Before the first run, check the data for duplicate identifiers, missing
  parents and empty keys.
tags: mapping, identifiers, human_friendly_id, upsert, sync-config, data-check
---

## Make Sync Identifiers Match the Destination Human-Friendly ID

In the customer's sync configuration, the `identifiers`
of each `schema_mapping` entry are the fields of the
destination kind's `human_friendly_id`: one identifier
per HFID element, named after the element's first
segment (`location__name__value` gives `location`), in
the same order. When the node declares no
`human_friendly_id`, use the one it inherits from a
generic listed in `inherit_from`.

### Why it matters

The sync keys records on `identifiers`, but the
infrahub-sync Infrahub adapter saves each node with
`allow_upsert=True`, and Infrahub matches an upsert on
the human-friendly ID, not on the sync key. When the two
differ, two source records that share an HFID become one
node:

- **Microsoft Graph.** The sync keyed users on the Graph
  object ID while the HFID was `username`. Two accounts
  with the same user name on two domains were merged into
  one node. The log said "Created successfully", and every
  full run overwrote one with the other.

Nothing reports the merge. The diff shows two creates,
and Infrahub holds one node.

### How to apply

1. **Find the HFID** of every destination kind in the
   schema loaded on Infrahub, or in the customer
   repository's `schemas/`. When the node has no
   `human_friendly_id`, take it from the first generic
   in its `inherit_from` that declares one.
2. **Set `identifiers`** to the first segment of each HFID
   element, in order. The fields of those names must be
   in the entry's `fields`.
3. **Keep the source's stable ID as an ordinary field**
   (`object_id`, `webex_id`) when the schema has an
   attribute for it. It is not the key.
4. **When the user wants the stable source ID as the
   key**, for example because records are renamed often,
   explain the trade-off:
   - Keyed on the HFID, a renamed record looks like one
     deletion and one creation. The infrahub-sync
     Infrahub adapter does not delete, so the old node
     stays (see
     [../reference.md](../reference.md#known-infrahub-sync-core-limits)).
   - Keyed on the source ID, the HFID has to become that
     ID, which is a schema change.

   Then either keep `identifiers` equal to the HFID, or
   propose the HFID change through
   `infrahub-managing-schemas` and wait for the user's
   approval of the schema before changing `identifiers`.
   Never leave the two different.

The HFID rules themselves are in
[../../infrahub-managing-schemas/rules/display-human-friendly-id.md](../../infrahub-managing-schemas/rules/display-human-friendly-id.md),
and how a reference names a peer by its HFID is in
[../../infrahub-managing-objects/rules/value-relationships.md](../../infrahub-managing-objects/rules/value-relationships.md).

### Correct

The destination `LocationMeetingRoom` inherits
`human_friendly_id: [parent__name__value, name__value]`
from a generic:

```yaml
schema_mapping:
  - name: LocationMeetingRoom
    mapping: /v1/workspaces
    identifiers: [parent, name]
    fields:
      - {name: parent, mapping: locationId, reference: LocationSite}
      - {name: name, mapping: displayName}
      - {name: webex_id, mapping: id}
```

### Incorrect

Keyed on the source ID while the HFID is
`[parent__name__value, name__value]`. Two rooms with the
same name in the same site are merged into one node:

```yaml
schema_mapping:
  - name: LocationMeetingRoom
    mapping: /v1/workspaces
    identifiers: [webex_id]
    fields:
      - {name: webex_id, mapping: id}
      - {name: parent, mapping: locationId, reference: LocationSite}
      - {name: name, mapping: displayName}
```

### Data check before the first run

Matching keys are not enough when the data breaks them.
In infrahub-sync, one bad record stops the whole run,
and `--continue-on-error` does not help. On the Webex
sync:

- two locations with the same site code raised
  `ObjectAlreadyExists`;
- a room whose parent site was not in Infrahub failed
  with `NODE_NOT_FOUND` after 188 of 621 rooms;
- an empty identifier fails with "mapped identifiers must
  have nonempty values".

Before the first `diff`, read every record once with the
adapter's client, outside the repository, apply the
entry's filters and transforms, and report every
problem at once, not the first one:

```python
from collections import Counter


def precheck(records: list[dict], identifiers: list[str], parent_field: str | None, known_parents: set) -> dict:
    """records: one dict per source record, with the mapped field values the sync will send."""
    keys = [tuple(record.get(field) for field in identifiers) for record in records]
    return {
        "duplicate_identifiers": [key for key, count in Counter(keys).items() if count > 1],
        "empty_identifiers": [key for key in keys if any(value in (None, "") for value in key)],
        "missing_parents": sorted(
            {record.get(parent_field) for record in records if record.get(parent_field) not in known_parents}
        )
        if parent_field
        else [],
    }
```

`known_parents` holds the parent keys loaded earlier in
the same sync and the parents already in Infrahub. Show
the counts and examples to the user, who decides: clean
the source data, or exclude the records with a filter for
the test only. Temporary filters do not stay in the
committed configuration.

### Common mistakes

- **Reading the HFID from the node only**, and missing
  the one it inherits from a generic.
- **Keying on the source ID because the user asks for
  it**, without the schema change that makes it the HFID.
- **Keeping only part of the HFID**, such as `[name]`
  when the HFID is `[name__value, location__name__value]`.
- **Finding data problems one run at a time** instead of
  with one check before the first run.

Reference: [Infrahub documentation](https://docs.infrahub.app)
