---
title: Menu File Structure
impact: CRITICAL
tags: format, apiVersion, kind, Menu, spec
---

## Menu File Structure

Impact: CRITICAL

Menu files need a fixed `apiVersion` / `kind` /
`spec.data` envelope. Deviations are rejected at
load time.

### Why it matters

Infrahub parses every menu file through a strict
Pydantic model: missing `apiVersion`, the wrong
`kind`, or items outside `spec.data` cause the
menu to fail to load entirely — the sidebar then
falls back to the auto-generated menu, masking the
intent of the custom file. Including the
`.infrahub.yml` registration comment and the
`include_in_menu: false` advice in the output is
what saves the user from a second confused round
trip when their menu "doesn't show up".

### Required Fields

| Field        | Value             | Description                   |
| ------------ | ----------------- | ----------------------------- |
| `apiVersion` | `infrahub.app/v1` | Always this value             |
| `kind`       | `Menu`            | Always `Menu` for navigation  |
| `spec.data`  | list              | Array of top-level menu items |

### Correct

```yaml
# yaml-language-server:
#   $schema=https://schema.infrahub.app/infrahub/menu/latest.json
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceMenu
      label: Devices
      icon: "mdi:server"
      kind: DcimDevice
```

### .infrahub.yml Registration

The menu file must be registered in `.infrahub.yml`
under the `menus:` key. Always include this as a
YAML comment in the output file so the user knows:

```yaml
# Register this file in .infrahub.yml:
#
#   menus:
#     - menus/menu-full.yml
```

> **Common typo: `menu:` (singular) instead of
> `menus:` (plural).** The `.infrahub.yml`
> validator is `additionalProperties: false`, so a
> singular key is rejected with
> `menu: extra_forbidden`. The plural form
> propagated through several repo skeletons and
> templates, so this is a high-frequency mistake
> when copy-pasting into a new project. The key is
> always `menus:`, matching `queries:`,
> `check_definitions:`, `python_transforms:`,
> `jinja2_transforms:`, and
> `artifact_definitions:` — all plurals.

### Removing or Renaming Items

Taking an item out of the file does not always take
it out of Infrahub. What removes it depends on how the
file got there. A rename (new `name` or `namespace`)
counts as removing the old item and adding a new one.

| File loaded by | Items dropped from the file | Do |
| -------------- | --------------------------- | -- |
| A `CoreRepository` syncing a `menus:` entry in `.infrahub.yml` (Infrahub 1.3+) | Deleted by the next sync | Commit and push. Do not delete them by hand. |
| A `CoreReadOnlyRepository` (Infrahub 1.3+) | Stay until it re-imports; a push alone does not trigger that | Push, then update the repository's `commit` (or `ref`) so it re-imports and deletes them |
| `infrahubctl menu load` | Stay on the instance; the load only creates and updates, and still succeeds | Delete each one |

A sync removes only items it loaded itself. An item
loaded with `infrahubctl menu load` from a file the
repository never had is not the sync's to remove, even
in a git-synced project: delete it explicitly.

Delete one item per command, by `namespace/name`
(infrahubctl 1.20+):

```bash
infrahubctl object delete CoreMenuItem Dcim/RackMenu --yes
```

On `No such command`, upgrade infrahubctl, or delete
through GraphQL with
`CoreMenuItemDelete(data: {hfid: ["Dcim", "RackMenu"]})`.

Deleting a group header leaves its children behind, so
delete each child too. Items in the `Builtin` namespace
are protected and cannot be deleted.

The leftovers are silent: the load or sync succeeds and
every wanted entry is there, so nobody notices the old
ones until they count the sidebar.

Incorrect: the file is git-synced, and the steps
hand-delete what the next sync removes anyway:

```bash
git push origin main
infrahubctl object delete CoreMenuItem Dcim/RackMenu --yes
```

Correct: push, and delete only what the sync never
loaded:

```bash
git push origin main
infrahubctl object delete CoreMenuItem Dcim/TempLabMenu --yes
```

### Key Rules

- Include the `$schema` comment for IDE validation
- Include `.infrahub.yml` registration comment
- Include `include_in_menu: false` advice comment
- One menu file per project typically
- The menu is merged into the sidebar Infrahub already
  builds; it does not replace it
  (see [hierarchy-nesting.md](./hierarchy-nesting.md))

Reference: [infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
