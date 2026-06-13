# Value Metadata: Source, Owner, and Protection

Every attribute and relationship value in Infrahub
carries **metadata** that records where the value came
from, who is responsible for it, and whether it is
locked. This is shared reference material: it applies
anywhere a value is written (object data files,
generators) or read (queries, analysis).

The three writable metadata fields are `source`,
`owner`, and `is_protected`. Getting their roles right
matters because they are easy to confuse — and the most
common confusion (that `source` restricts edits) is
wrong and misleads users.

## The three fields

| Field | Question it answers | Accepted node kinds | Controls write access? |
| ----- | ------------------- | ------------------- | ---------------------- |
| `source` | "Where did this value come from?" | `Account`, `Repository` | **No** — lineage label only |
| `owner` | "Who is responsible for this value?" | `Group`, `Account`, `Repository` | Yes — but only when `is_protected` is set |
| `is_protected` | "Is this value locked?" | boolean | Yes — enforces owner-only edits |

### source — lineage only

`source` records the origin of a data point (e.g. an
import script, a sync tool's account, or a repository).
It is **purely informational and has no access-control
effect**. Setting `source` never restricts who can edit
the value.

### owner — responsibility, and the lock holder

`owner` designates who manages a data point. On its own
`owner` is also informational. It becomes meaningful for
access control **only in combination with**
`is_protected`.

### is_protected — the actual lock

When `is_protected: true` on a value, **only the owner
(and accounts with the `admin` role) can modify that
specific attribute**. Other attributes on the same
object remain editable. Protection is tied exclusively
to `owner` — `source` plays no part.

## The key misconception

**`source` does not control who can edit data.**

A frequent mistake is assuming that stamping `source`
on synced or imported data will stop humans from
changing it. It will not. Lineage and access control
are separate concerns:

- To **lock** a value so only one team can change it:
  set `owner` to that team's group **and**
  `is_protected: true`.
- To merely **record provenance**: set `source`. The
  owner can still freely edit the value afterward.

Conversely, marking a value protected does not change
its `source`; the two are independent.

## Common patterns

| Scenario | source | owner | is_protected |
| -------- | ------ | ----- | ------------ |
| One-time import, then human-maintained | sync tool (lineage) | responsible team/group | `true` — only that group edits |
| Continuously synced from an external system | sync tool | sync tool | `true` — blocks manual overrides |
| Manually created data | creating user | responsible team/group | `true` or `false` per policy |
| Reference/seed data nobody should change | admin account | admin account | `true` |

## Setting metadata in object files

In an object data file, write the attribute as a mapping
with `value` plus any metadata keys, instead of a plain
scalar. `source` and `owner` reference an existing node
(an `Account`, `Repository`, or `Group`) the same way
any related object is referenced — the node must already
exist when the value loads.

```yaml
spec:
  kind: DcimDevice
  data:
    - name: spine-01           # plain scalar — no metadata
      role:                    # mapping form — value + metadata
        value: leaf
        source: netbox-sync     # lineage: where it came from
        owner: network-team     # responsible group
        is_protected: true      # locked: only network-team (+admins) can edit
      status: active           # editable by anyone
```

Only the attributes you write as a mapping carry
metadata; the rest stay plain scalars and remain freely
editable.

## Reading metadata in queries

Attribute metadata is queryable in GraphQL alongside the
value. The lineage fields hang off the attribute, not
the node:

```graphql
DcimDevice {
  edges {
    node {
      role {
        value
        is_protected
        source { display_label }
        owner { display_label }
      }
    }
  }
}
```

This is distinct from **object-level metadata**
(`created_at`, `created_by`, `updated_at`, `updated_by`),
which tracks the lifecycle of the whole node and is
accessed via `node_metadata` on the edge — see
[graphql-queries.md](./graphql-queries.md).
