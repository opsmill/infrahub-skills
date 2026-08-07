---
title: Author Schema Keys in the Canonical Order
impact: MEDIUM
tags: format, ordering, diffs, infrahubctl, tooling
---

## Author Schema Keys in the Canonical Order

Impact: MEDIUM

Write the keys of every node, generic, attribute,
relationship, and dropdown choice in one canonical order,
and let `infrahubctl schema format` apply it when the
installed `infrahubctl` provides that command.

### Why it matters

Schema files are edited constantly, and each edit tends to
append new keys wherever the cursor happens to be. The
result is that `kind`, `optional`, and `order_weight` move
around between commits, so the diff shows a dozen relocated
lines and the one substantive change — a new attribute, a
changed `peer` — is buried in the noise. Reviewers stop
reading carefully, which is exactly when a wrong
`identifier` or a dropped `optional: false` slips through.

A single canonical order fixes this: two people editing the
same node produce the same layout, and the diff contains
only what actually changed.

The order is **cosmetic**. It moves lines; it never changes
what the schema means. That makes it safe to apply to an
existing repository in one pass, unlike anything that
touches values.

### The canonical order

Top-level keys:

```text
version → generics → nodes → extensions
```

Within a node or generic — identity first, the long lists
last:

```text
name → namespace → description → label → icon →
documentation → include_in_menu → menu_placement →
inherit_from → parent → children → hierarchical →
default_filter → human_friendly_id → order_by →
display_label → uniqueness_constraints →
generate_profile → generate_template → branch → state →
attributes → relationships
```

Within an attribute: `name` → `kind` → `label` →
`unique` → `read_only` → `computed_attribute` →
`default_value` → `choices` → `regex` → `min_length` /
`max_length` → `parameters` → `optional` → `description`
→ … → `order_weight` **last**.

Within a relationship: `name` → `peer` → `label` →
`kind` → `cardinality` → `optional` → `identifier` →
`direction` → `on_delete` → … → `order_weight` **last**.

Within a dropdown choice: `name` → `label` →
`description` → `color`.

Within an entry under `extensions.nodes`, the target
`kind` leads and the lists come last: `kind` →
`attributes` → `relationships`. The attributes and
relationships inside it take the same order as anywhere
else. (An extension carries nothing else worth ordering —
[extension-cross-file.md](./extension-cross-file.md)
explains why `attributes` and `relationships` are the only
keys it can usefully hold.)

Any key not named above keeps its position between the
leading and trailing groups, so nothing is ever dropped.
List *items* are never reordered — attributes and
relationships keep the grouping you authored.

This rule governs *where* `order_weight` sits in the key
list. It says nothing about the value:
[display-order-weight.md](./display-order-weight.md)
owns that (key relationships 800–900, core attributes
1000–1999, and so on, with gaps left for inserts).

### Example

Non-compliant — keys scattered, `order_weight` mid-block,
`attributes` ahead of the node's own identity keys:

```yaml
---
version: "1.0"
nodes:
  - namespace: Dcim
    attributes:
      - order_weight: 1000
        name: name
        unique: true
        kind: Text
      - name: status
        order_weight: 1500
        kind: Dropdown
        choices:
          - color: "#7fbf7f"
            name: active
            label: Active
    name: PatchPanel
    display_label: name__value
    human_friendly_id:
      - name__value
```

Compliant — same schema, canonical order:

```yaml
---
version: "1.0"
nodes:
  - name: PatchPanel
    namespace: Dcim
    human_friendly_id:
      - name__value
    display_label: name__value
    attributes:
      - name: name
        kind: Text
        unique: true
        order_weight: 1000
      - name: status
        kind: Dropdown
        choices:
          - name: active
            label: Active
            color: "#7fbf7f"
        order_weight: 1500
```

### Applying it with infrahubctl

`infrahubctl schema format` writes this order for you and
runs **offline** — unlike `schema check` and `schema load`,
it never contacts a server, so it works in CI and on a
laptop with no instance running. It formats only your own
nodes; anything in an Infrahub-reserved namespace (`Core`,
`Builtin`, `Internal`, `Profile`, `Template`, …) is left
untouched, and it aborts on a file rather than write a
change it cannot prove is meaning-preserving.

Format before `schema check` / `schema load`, so the file
committed to git is already canonical.

The command is newer than the rest of the `schema`
subcommands. Confirm it exists before making it a
documented step in a project:

```bash
infrahubctl schema format --help
```

If that reports `No such command 'format'`, the installed
`infrahub-sdk` predates the command — upgrade it, or apply
the order above by hand. The order is the rule; the command
is a convenience.

The invocations, flags, and the CI gate (`--check`) live in
[../validation.md](../validation.md).

### Common mistakes

- Reaching for `--backfill-order-weight` to "fix" missing
  weights. It writes the single constant `1000` to every
  unweighted attribute *and* relationship — which collapses
  the ranges
  [display-order-weight.md](./display-order-weight.md)
  exists to keep apart (relationships belong in 800–900 or
  3000+) and leaves no gaps for future inserts. If you use
  it, re-spread the values by hand afterwards.
- Assuming the other opt-in flags are cosmetic too.
  `--strip-defaults` and `--sort-by-order-weight` change
  file *content*, not just line order; they are off by
  default for that reason.
- Expecting standalone comments to survive
  `--sort-by-order-weight`. In the default (key-ordering)
  mode, comments, quoting, and inline sequences like
  `[manufacturer, name__value]` are all preserved. Once
  that flag reorders list items, a standalone comment
  sitting *between* two attributes may not follow the item
  it described — inline comments on a value always travel
  with it.
- Running the formatter on a multi-document YAML file and
  expecting a result. Those files are skipped, not
  reformatted.
- Reading a first `--check` failure as "our key order is
  wrong". Files with no `# yaml-language-server` directive
  get one prepended, so a repository that has never been
  formatted fails the gate on the header alone. Format
  once, commit, then turn the gate on.
- Treating formatting as the review step. A canonical file
  can still be a wrong schema — `schema check` on a branch
  is what validates it, per
  [workflow-branch-first.md](./workflow-branch-first.md).

Reference:
[infrahubctl schema](https://docs.infrahub.app/infrahubctl/infrahubctl-schema)
