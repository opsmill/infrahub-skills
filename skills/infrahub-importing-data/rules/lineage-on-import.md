---
title: Optional Lineage Stamping at Import
impact: LOW
description: >-
  If the user opts in during the interview, stamp every imported value with
  source: <import-tag> using the value+metadata mapping form. source is
  lineage only; locking requires owner + is_protected: true.
tags: lineage, source, owner, metadata, import-tag
---

## Optional Lineage Stamping at Import

Impact: LOW

If the user opts in during the interview, stamp
every imported value with `source: <import-tag>`
using the value+metadata mapping form. Make clear
in the same interview question that `source` is
lineage only — it does not lock the value or
restrict who can edit it. To lock imported data,
the user must also set `owner` and `is_protected:
true`.

The full metadata semantics live in
[../../infrahub-common/metadata-lineage.md](../../infrahub-common/metadata-lineage.md);
the emission form is documented in
[../../infrahub-managing-objects/rules/value-attributes.md](../../infrahub-managing-objects/rules/value-attributes.md)
under the value-metadata pattern. This rule covers
the CSV-import-specific concerns.

### Why it matters

Imports are a natural place to stamp lineage —
six months from now, looking at a value in the
UI, the user wants to know "this came from
csv-import-20260621-1430, not from a sync or a
hand edit." That's what `source` is for, and it's
cheap to do at emission time.

But `source` is **purely informational**. The
common misconception ("I'll stamp source on
imported data so humans can't change it later") is
wrong and load-bearing in the worst way: users
treat their imports as locked when they aren't. A
team can edit anything on the device the next day
and the source tag stays put, giving a false sense
of locked-in provenance.

The CSV-import skill is well-positioned to make
this distinction clear because the user is making
the decision in real time, in the interview.

### The interview question

```text
Stamp every imported value with a lineage tag?

  a) No — emit plain scalars.
  b) Yes, source only — stamps provenance but does
     NOT restrict edits. Anyone with normal write
     access can still change these values
     afterward.
  c) Yes, source + lock — stamps provenance AND
     marks the value as owner-only-editable
     (requires choosing an owner Group/Account
     and setting is_protected: true).

For (b) or (c), pick the source reference:
  - csv-import-20260621-1430 (default: a new Account)
  - <some-existing-Account-or-Repository>
```

### Emission shape: lineage only (option b)

Each attribute becomes a `value` + metadata
mapping:

```yaml
spec:
  kind: OrganizationManufacturer
  data:
    - name:
        value: Dell
        source: csv-import-20260621-1430
      description:
        value: Server and storage vendor
        source: csv-import-20260621-1430
      country:
        value: US
        source: csv-import-20260621-1430
```

Only attributes you write as a mapping carry
metadata; plain scalars stay plain and freely
editable.

### Emission shape: source + lock (option c)

```yaml
spec:
  kind: OrganizationManufacturer
  data:
    - name:
        value: Dell
        source: csv-import-20260621-1430
        owner: network-team
        is_protected: true
      description:
        value: Server and storage vendor
        source: csv-import-20260621-1430
        owner: network-team
        is_protected: true
```

Locking attaches to `owner` + `is_protected: true`;
`source` plays no part in access control.

### The source reference must exist

`source` is a reference to an `Account` or
`Repository` node — it has to exist on the target
branch before the load runs, or the reference
fails to resolve. The skill has two ways to handle
this:

1. **Pre-existing source.** If the user picks an
   existing `Account` or `Repository`, just
   reference it.
2. **Bootstrap a new Account.** If the default
   tag (`csv-import-YYYYMMDD-HHMM`) doesn't exist
   yet, emit `output_dir/00_lineage_accounts.yml`
   ahead of the data files. The `00_` prefix
   guarantees it loads first; the load order
   rules in
   [../../infrahub-managing-objects/rules/organization-load-order.md](../../infrahub-managing-objects/rules/organization-load-order.md)
   keep the loader from racing.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreAccount
  data:
    - name: csv-import-20260621-1430
      type: Script
      description: One-time CSV import on 2026-06-21
```

### Common mistakes

- **Stamping `source` and assuming the data is
  locked.** It isn't. Locking needs `owner` +
  `is_protected: true`.
- **Forgetting the source reference must exist.**
  The load fails with a reference-not-found error
  if the named Account hasn't been created.
- **Stamping every attribute when only a few
  matter.** Lineage on a row's `name` and a few
  attributes is often enough; stamping every
  attribute makes the file longer than it needs
  to be. Confirm the per-attribute granularity in
  the interview if it's not obvious.
- **Hand-rolling a different source-reference
  shape.** The `value`+metadata mapping form is
  the only shape the loader accepts; nesting
  `metadata: { source: ... }` doesn't work.

Reference: [Value Metadata](../../infrahub-common/metadata-lineage.md)
