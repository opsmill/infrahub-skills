---
title: Menu Hierarchy and Nesting
impact: HIGH
tags: hierarchy, nesting, children, data, group-headers, parent, builtin-sections
---

## Menu Hierarchy and Nesting

Impact: HIGH

Nested menu items live under `children.data`, never
directly under `children`. Top-level items sit beside
the sections Infrahub already ships, never on top of
them.

### Why it matters

The menu schema models children as an object that
carries pagination metadata alongside the `data`
list — the same shape every paginated Infrahub
GraphQL response uses. Putting a bare list under
`children` makes the parser reject that branch; the
sidebar renders the parent as a clickable leaf with
no children, which looks to the user like the
sub-items "disappeared". The wrapper is also what
lets future versions extend children with filtering
or pagination without reshaping existing menu files.

### Incorrect -- children without data wrapper

```yaml
- namespace: Dcim
  name: DeviceMenu
  children:
    - namespace: Dcim        # Wrong! Must be under `data`
      name: Servers
```

### Correct -- children with data wrapper

```yaml
- namespace: Dcim
  name: DeviceMenu
  label: Device Management
  icon: "mdi:server"
  children:
    data:                          # Required wrapper
      - namespace: Dcim
        name: InfrastructureMenu
        label: "Infrastructure"
        icon: "mdi:server"
        children:
          data:
            - namespace: Dcim
              name: Server
              label: Servers
              kind: DcimServer
              icon: mdi:server

            - namespace: Dcim
              name: Switch
              label: Switches
              kind: DcimSwitch
              icon: mdi:switch

      - namespace: Dcim
        name: TypesMenu
        label: "Types & Platforms"
        icon: "mdi:cog"
        children:
          data:
            - namespace: Organization
              name: Manufacturer
              label: Manufacturers
              kind: OrganizationManufacturer
              icon: "mdi:factory"
```

### Infrahub Already Owns Part of the Tree

A custom menu is merged into the menu Infrahub ships,
not laid over an empty sidebar. The sidebar has two
areas, and only one of them is yours.

**Object area** (Infrahub 1.11). Your nodes belong here,
and these are the only sections worth attaching to:

| Identifier | Sidebar label |
| ---------- | ------------- |
| `BuiltinOther` | Other |
| `BuiltinIPAM` | IPAM |

**Infrahub's own area.** These carry platform features,
not user data. Do not attach object nodes to them, and
do not redeclare them:

| Identifier | Sidebar label |
| ---------- | ------------- |
| `BuiltinProposedChanges` | Proposed Changes |
| `BuiltinBranches` | Branches |
| `BuiltinObjectManagement` | Object Management |
| `BuiltinActions` | Actions |
| `BuiltinIntegration` | Integrations |
| `BuiltinActivity` | Activity |
| `BuiltinAdmin` | Admin |

Declaring an `IPAM` section of your own puts a second
one in the sidebar beside the shipped one. Users read
that as a broken menu, and unlike the auto-menu
duplicates in
[schema-integration.md](./schema-integration.md) there
is nothing to fix on the schema side: the duplicate is
the custom file itself.

A label that clashes with a section in the second table
is fixed by relabelling, not by parenting into it. A
"Device Actions" group is fine; a second plain "Actions"
heading is not.

### Nesting Under a Built-in Section

`parent` names the item to nest under by its
human-friendly ID, which for a menu item is its
namespace and name as a two-element list. Reach for it
when a node belongs in a section from the object table:

```yaml
- namespace: Ipam
  name: Vlans
  label: VLANs
  kind: IpamVlan
  icon: "mdi:lan"
  parent: [Builtin, IPAM]     # under the shipped IPAM section
```

A group attaches the same way and carries its children
with it:

```yaml
- namespace: Ipam
  name: Addressing
  label: Addressing
  icon: "mdi:ip-network-outline"
  parent: [Builtin, IPAM]
  children:
    data:
      - namespace: Ipam
        name: Vrf
        label: VRFs
        kind: IpamVrf
        icon: "mdi:router-network"
```

Both elements are matched exactly, so `[Builtin, Ipam]`
finds nothing and the load fails with a lookup error on
that item.

#### Incorrect -- recreating a shipped section

```yaml
- namespace: Builtin        # Wrong! Builtin is a restricted
  name: IPAM                # namespace and the load is rejected
  label: IPAM
  children:
    data:
      - namespace: Ipam
        name: Vlan
        kind: IpamVlan
```

`Builtin` is reserved, so this fails outright with
"Builtin is not valid, it's a restricted namespace"
rather than producing the duplicate. The duplicate is
what you get from the version that *does* load: the same
heading under a namespace of your own.

#### Incorrect -- a second IPAM heading under your own namespace

```yaml
- namespace: Ipam           # Loads fine, and that is the problem:
  name: Management          # the sidebar now shows IPAM twice
  label: IPAM
  children:
    data:
      - namespace: Ipam
        name: Vlan
        kind: IpamVlan
```

Give the group a label of its own, or attach the items
to the shipped section with `parent:` when they really
belong inside it.

### Planning a Hierarchy

Start from the sections above, not from a blank tree,
then map out what you are adding:

```text
Device Management
  ├── Infrastructure
  │   ├── Servers
  │   ├── Switches
  │   └── PDUs
  ├── Types & Platforms
  │   ├── Manufacturers
  │   └── Device Types
  └── Modules
      ├── Module Types
      └── Module Installations
```

### Key Rules

- `children` is the wrapper; `data` inside it
  carries the list of child items
- Children follow the identical property structure
  (unlimited nesting depth)
- Never recreate a section Infrahub ships; give the
  group its own label, or attach to `Other` or `IPAM`
  with `parent: [<Namespace>, <Name>]`
- Use YAML comments for readability in large menus
  (`# --------- Section ---------`)

Reference:
[Infrahub Menu Docs](https://docs.infrahub.app)
