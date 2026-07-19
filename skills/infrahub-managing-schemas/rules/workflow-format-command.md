---
title: Format Schema Files with `infrahubctl schema format`
impact: MEDIUM
tags: workflow, formatting, ordering, tooling
---

## Format Schema Files with `infrahubctl schema format`

Impact: MEDIUM

Run `infrahubctl schema format` to normalise the key
ordering of hand-authored schema files instead of
ordering keys by hand.

### Why it matters

Schema files are edited constantly, and every edit
reshuffles the order of keys within nodes, attributes,
and relationships. That drift produces noisy diffs that
bury the substantive change and makes review harder. The
formatter imposes one opinionated, canonical key order —
`name`/`namespace` first, `attributes` then
`relationships` last, `order_weight` last within each
attribute/relationship, `choices` as
`name`/`label`/`description`/`color` — so files read the
same way and diffs stay small. It automates the ordering
convention documented in
[display-order-weight.md](./display-order-weight.md).

Unlike `schema check` and `schema load`, this command is
**offline** — it never contacts a server.

### What it does

- Reorders the **keys** within each node, generic,
  attribute, relationship, and dropdown choice into the
  canonical order. It never reorders the list items
  themselves (attributes and relationships keep their
  authored grouping).
- Formats only your own nodes. Nodes and generics in an
  Infrahub-reserved namespace (`Core`, `Builtin`,
  `Internal`, `Profile`, `Template`, …) are left
  untouched.
- **Preserves comments** (the `# yaml-language-server`
  header, standalone notes, and inline comments), quoting
  style, and inline (flow) sequences such as
  `[manufacturer, name__value]`. The resulting diff is
  therefore purely key reordering. If the `$schema` header
  is missing it is added.

### Usage

```bash
# Format a whole directory in place
infrahubctl schema format schemas/

# Preview the changes without writing
infrahubctl schema format schemas/dcim.yml --diff

# CI gate: exit 1 if any file is not formatted (writes nothing)
infrahubctl schema format schemas/ --check
```

Format before `schema check` / `schema load` so the file
committed to git is already in canonical form.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
