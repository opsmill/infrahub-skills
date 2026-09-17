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
not laid over an empty sidebar. These top-level sections
exist before your file loads (Infrahub 1.11):

| Identifier | Sidebar label |
| ---------- | ------------- |
| `BuiltinOther` | Other |
| `BuiltinIPAM` | IPAM |
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

### Nesting Under a Built-in Section

`parent` takes the identifier of the item to nest under,
which is its namespace and name concatenated. Reach for
it whenever a node belongs in a section Infrahub already
provides:

```yaml
- namespace: Ipam
  name: Vlans
  label: VLANs
  kind: IpamVlan
  icon: "mdi:lan"
  parent: BuiltinIPAM      # under the shipped IPAM section
```

A group attaches the same way and carries its children
with it:

```yaml
- namespace: Ipam
  name: Addressing
  label: Addressing
  icon: "mdi:ip-network-outline"
  parent: BuiltinIPAM
  children:
    data:
      - namespace: Ipam
        name: Vrf
        label: VRFs
        kind: IpamVrf
        icon: "mdi:router-network"
```

The value is matched exactly. `BuiltinIpam` resolves to
nothing, and the item is dropped with an "unable to find
the parent menu item" log line rather than an error.

#### Incorrect -- recreating a shipped section

```yaml
- namespace: Builtin        # Wrong! BuiltinIPAM already exists
  name: IPAM
  label: IPAM
  children:
    data:
      - namespace: Ipam
        name: Vlan
        kind: IpamVlan
```

Changing the namespace does not rescue it. A top-level
item labelled `IPAM` still reads as a duplicate section
in the sidebar whatever its identifier, so the fix is
`parent:`, not a fresh name.

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
- Never recreate a section Infrahub ships; attach to it
  with `parent: <Namespace><Name>`
- Use YAML comments for readability in large menus
  (`# --------- Section ---------`)

Reference:
[Infrahub Menu Docs](https://docs.infrahub.app)
