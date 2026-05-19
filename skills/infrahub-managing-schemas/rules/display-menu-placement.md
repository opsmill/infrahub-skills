---
title: Menu Placement and Hidden Nodes
impact: MEDIUM
tags: display, menu_placement, include_in_menu, navigation, generic
---

## Menu Placement and Hidden Nodes

Impact: MEDIUM

The Infrahub UI builds its sidebar from two
sources: the default per-kind menu (one entry per
node/generic) and **explicit menu files** declared
under `menus:` in `.infrahub.yml`. The two
strategies are mutually exclusive in practice — pick
one and apply it consistently.

| Property | Effect |
| -------- | ------ |
| `include_in_menu: false` | Excludes the node/generic from the default per-kind sidebar |
| `menu_placement: <FullKind>` | Within the default sidebar, nests this node under another node's menu entry |

### Strategy A — Explicit Menu Files (Recommended)

When the project ships menu YAML files (registered
under `menus:` in `.infrahub.yml`), the menu is
authored by hand and the per-kind defaults only get
in the way. **Set `include_in_menu: false` on every
node and generic.** The menu file is the single
source of truth; nothing should leak through from
the schema.

```yaml
nodes:
  - name: Device
    namespace: Dcim
    include_in_menu: false        # Always, when menu files are used
    ...
  - name: Interface
    namespace: Dcim
    include_in_menu: false
    ...

generics:
  - name: GenericDevice
    namespace: Dcim
    include_in_menu: false
    ...
```

Then drive what the user actually sees from the menu
file (see the
[infrahub-managing-menus](../../infrahub-managing-menus/SKILL.md)
skill).

### Strategy B — Per-Kind Default Sidebar

When there is no menu file, Infrahub auto-generates
a sidebar from the schema. In that mode, you
selectively hide nodes that should not surface and
group subtypes under their parents:

**Hide abstract bases and mixins** so users don't
see types they cannot instantiate:

```yaml
generics:
  - name: PhysicalDevice
    namespace: Dcim
    include_in_menu: false        # Abstract — never instantiated

  - name: Endpoint
    namespace: Dcim
    include_in_menu: false        # Mixin

  - name: Layer2
    namespace: Interface
    include_in_menu: false        # Trait mixin
```

**Group concrete subtypes under a parent** so they
share one sidebar entry instead of cluttering the
top level:

```yaml
nodes:
  - name: RearPatchPanelInterface
    namespace: Dcim
    label: Patch Panel Rear Interfaces
    menu_placement: DcimGenericPatchPanelInterface

  - name: FrontPatchPanelInterface
    namespace: Dcim
    label: Patch Panel Front Interfaces
    menu_placement: DcimGenericPatchPanelInterface
```

Common menu-placement targets in production:

| Parent kind | Typical children |
| ----------- | ---------------- |
| `LocationGeneric` | Region, Site, Building, Rack |
| `OrganizationGeneric` | Provider, Customer, Tenant |
| `CloudResource` | VirtualNetwork, Subnet, Account |
| `ServiceGeneric` | Concrete service types |
| `RoutingBGPSession` | Peer-group session subtypes |

`menu_placement` is meaningful only in Strategy B —
it nests within the default sidebar, which menu
files replace.

### How To Tell Which Strategy Applies

Check `.infrahub.yml`:

```yaml
menus:
  - menus/menu-full.yml          # ← Menu file present → Strategy A
```

If `menus:` is populated, use Strategy A and hide
everything. If it's absent, use Strategy B and only
hide what shouldn't appear.

### Antipatterns

**Mixing strategies:** menu files declared in
`.infrahub.yml` *and* nodes left at default visibility.
The user sees a hand-authored menu plus an unwanted
auto-generated tail of every other kind.

**Forgetting to hide newly added kinds when menu
files are in use:** the menu file is fine but the
schema sneaks new entries into the sidebar each time
a node is added. Treat `include_in_menu: false` as
the default for every new node/generic in
menu-driven projects.

**Using `menu_placement` with a kind that has
`include_in_menu: false`:** the menu entry the child
points to does not exist (Strategy B), and the
subtype is orphaned. Either expose the parent or
pick a different placement target. In Strategy A
this property is moot — `menu_placement` has no
effect when the parent is hidden anyway.

Reference:
[Infrahub Schema Docs](https://docs.infrahub.app)
