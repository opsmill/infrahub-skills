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

### Key Rules

- Include the `$schema` comment for IDE validation
- Include `.infrahub.yml` registration comment
- Include `include_in_menu: false` advice comment
- One menu file per project typically
- The menu replaces the auto-generated sidebar
  navigation

Reference: [infrahub-yml-reference.md](../../infrahub-common/infrahub-yml-reference.md)
