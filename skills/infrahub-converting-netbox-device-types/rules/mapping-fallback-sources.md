---
title: Declare Precedence When Fields Compete
impact: HIGH
tags: mapping, fallback, precedence, shadowing
---

## Declare Precedence When Fields Compete

Impact: HIGH

When two NetBox fields target the same Infrahub
attribute, declare one as the other's `fallback`
rather than mapping both. The profile rejects an
undeclared collision.

### Why it matters

NetBox carries more free-text fields than most
Infrahub schemas have places to put them. A device
type has both `description` and `comments`; an
interface has both `label` and `description`. Against
schema-library each pair competes for a single
`description` attribute.

Map both and the last one silently wins — a mapping
order nobody chose, producing output that looks fine
and quietly discards whichever field lost. Map only
one and you lose every record that populated the
other: in the published library, `comments` is set on
66% of device types but `description` on only 4%, so
either choice alone throws away real data.

A declared fallback fixes both problems. The preferred
source wins when present, the fallback fills the gap
when it is not, and when *both* are set the loser is
reported as shadowed instead of vanishing.

### How to apply it

Pick the **semantic** match as the primary and the
merely-more-populated one as the fallback:

```yaml
device_type:
  fields:
    description:
      target: description
      fallback: comments      # or a list: [comments, notes]
```

`fallback` accepts a field name or an ordered list;
the first source carrying a non-empty value wins.
Every listed source counts as consumed, so none of
them show up as dropped.

**Wrong — two mappings racing for one target:**

```yaml
fields:
  description: description
  comments: description       # rejected: undeclared precedence
```

```text
error: Mapping profile: 'device_type.fields' maps both
'description' and 'comments' onto 'description'; declare one as
the other's 'fallback' so the precedence is explicit
```

**Wrong — dropping the more-populated field to keep
the tidier one:**

```yaml
fields:
  description: description    # loses `comments` on 66% of the library
```

### Common mistakes

- **Choosing the primary by how often it is
  populated.** Frequency picks the fallback; meaning
  picks the primary. A datasheet URL in the
  `description` attribute is worse than an empty one.
- **Listing a source as its own fallback**, or
  repeating a name in the list — both are rejected.
- **Treating a shadowed value as harmless.** It is a
  real discarded value; it belongs in the report, and
  [coverage-report-unmapped.md](./coverage-report-unmapped.md)
  applies to it.
