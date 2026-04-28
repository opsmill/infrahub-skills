# Infrahub Schema Examples

Real-world schema patterns extracted from production
Infrahub deployments. Use these as templates for common
infrastructure modeling scenarios.

## Organization Schema (Simplest Pattern)

A generic base with simple nodes inheriting from it.
Good starting point for any domain.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

generics:
  - name: Generic
    namespace: Organization
    label: Organization
    description: Base organization entity
    icon: mdi:domain
    include_in_menu: true
    human_friendly_id:
      - "name__value"
    order_by:
      - name__value
    display_label: name__value
    attributes:
      - name: name
        kind: Text
        unique: true
        order_weight: 1000
      - name: description
        kind: Text
        optional: true
        order_weight: 1200
    relationships:
      - name: tags
        peer: BuiltinTag
        cardinality: many
        kind: Attribute
        optional: true
        order_weight: 3000

nodes:
  - name: Manufacturer
    namespace: Organization
    description: Device and module manufacturer
    icon: mdi:factory
    inherit_from:
      - OrganizationGeneric
    include_in_menu: true
    menu_placement: OrganizationGeneric

  - name: TenantGroup
    namespace: Organization
    description: Grouping of tenants
    icon: mdi:folder-account
    inherit_from:
      - OrganizationGeneric
    include_in_menu: true
    menu_placement: OrganizationGeneric
    relationships:
      - name: tenants
        peer: OrganizationTenant
        kind: Component             # TenantGroup OWNS Tenants
        cardinality: many
        identifier: "tenantgroup__tenants"

  - name: Tenant
    namespace: Organization
    description: Tenant or customer organization
    icon: mdi:account-group
    inherit_from:
      - OrganizationGeneric
    include_in_menu: true
    menu_placement: OrganizationGeneric
    relationships:
      - name: group
        peer: OrganizationTenantGroup
        kind: Parent                # Tenant belongs to TenantGroup
        cardinality: one
        optional: false
        identifier: "tenantgroup__tenants"  # Must match Component side
```

**Key patterns:**

- Generic defines shared `name`, `description`, `tags`
- Nodes inherit and add specific relationships
- Component/Parent pair with matching `identifier`
- `menu_placement` groups nodes under the generic in the UI

---

## Hierarchical Location Schema

Location trees using `hierarchical: true`. Each level defines `parent` and `children`.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

generics:
  - name: Generic
    namespace: Location
    description: Generic Location
    label: Location
    icon: mingcute:location-line
    hierarchical: true             # Enables parent/children hierarchy
    include_in_menu: false
    order_by:
      - name__value
    display_label: "{{ name__value }}"
    attributes:
      - name: name
        kind: Text
        order_weight: 1000
        unique: true
      - name: shortname
        kind: Text
        unique: true
        order_weight: 1100
      - name: description
        kind: Text
        optional: true
        order_weight: 1200
      - name: status
        kind: Dropdown
        optional: true
        default_value: active
        order_weight: 1150
        choices:
          - name: active
            label: Active
            color: "#00FF00"
          - name: planned
            label: Planned
            color: "#0000FF"
          - name: staging
            label: Staging
            color: "#FFA500"
          - name: decommissioning
            label: Decommissioning
            color: "#808080"
    relationships:
      - name: tags
        peer: BuiltinTag
        kind: Attribute
        optional: true
        cardinality: many
        order_weight: 3000

nodes:
  - name: Region
    namespace: Location
    label: Region
    inherit_from:
      - LocationGeneric
    include_in_menu: false
    icon: "carbon:cics-region-target"
    parent: null                   # Root of hierarchy
    children: LocationSite
    uniqueness_constraints:
      - ["name__value"]

  - name: Site
    namespace: Location
    label: Site
    inherit_from:
      - LocationGeneric
    include_in_menu: false
    icon: mdi:office-building
    parent: LocationRegion
    children: LocationRoom
    uniqueness_constraints:
      - ["shortname__value", "parent"]   # Unique shortname within parent
    human_friendly_id:
      - parent__name__value              # Parent's name
      - shortname__value                 # This site's shortname
    attributes:
      - name: address
        kind: TextArea
        optional: true
        order_weight: 1100
      - name: timezone
        kind: Text
        optional: true
        order_weight: 1300
      - name: latitude
        kind: Number
        optional: true
        order_weight: 1400
      - name: longitude
        kind: Number
        optional: true
        order_weight: 1500

  - name: Room
    namespace: Location
    description: Room or area within a site
    inherit_from:
      - LocationGeneric
    include_in_menu: false
    icon: mdi:door
    parent: LocationSite
    children: LocationRack
    uniqueness_constraints:
      - ["name__value", "parent"]
    human_friendly_id:
      - parent__name__value
      - name__value

  - name: Rack
    namespace: Location
    description: Equipment rack
    inherit_from:
      - LocationGeneric
    include_in_menu: false
    icon: mdi:server
    parent: LocationRoom
    # No children - leaf of hierarchy
    uniqueness_constraints:
      - ["name__value", "parent"]
    human_friendly_id:
      - "parent__shortname__value"
      - "name__value"
    attributes:
      - name: height
        kind: Number
        default_value: 42
        description: Rack height in U
        order_weight: 1100
    relationships:
      - name: devices
        peer: DcimGenericDevice
        kind: Generic
        cardinality: many
        optional: true
        identifier: "rack__devices"
        on_delete: "no-action"
```

**Key patterns:**

- Generic has `hierarchical: true`
- Region has `parent: null` (root)
- Each level specifies `parent` and `children`
- Rack (leaf) has no `children`
- `uniqueness_constraints` scoped to parent: `["name__value", "parent"]`
- `human_friendly_id` traverses parent chain: `parent__name__value`

---

## Device Management with Generics and Inheritance

Complex schema showing multiple generics, computed attributes, and specialized nodes.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

generics:
  # Base device generic - shared by ALL device types
  - name: GenericDevice
    namespace: Dcim
    description: Physical device instance
    label: Device
    icon: mdi:server
    include_in_menu: false
    human_friendly_id:
      - name__value
    uniqueness_constraints:
      - ["rack", "rack_u_position__value"]
    attributes:
      - name: name
        kind: Text
        unique: true
        order_weight: 1000
      - name: serial
        kind: Text
        optional: true
        order_weight: 1100
      - name: asset_tag
        kind: Text
        optional: true
        order_weight: 1200
      - name: rack_u_position
        label: Rack Position (U)
        kind: Number
        optional: true
        order_weight: 1300
      - name: rack_face
        kind: Dropdown
        optional: true
        default_value: front
        order_weight: 1400
        choices:
          - name: front
            label: Front
          - name: rear
            label: Rear
      - name: status
        kind: Dropdown
        default_value: active
        order_weight: 1500
        choices:
          - name: active
            label: Active
            color: "#00FF00"
          - name: planned
            label: Planned
            color: "#0000FF"
          - name: staged
            label: Staged
            color: "#FFA500"
          - name: failed
            label: Failed
            color: "#FF0000"
          - name: decommissioning
            label: Decommissioning
            color: "#808080"
    relationships:
      - name: device_type
        peer: DcimDeviceType
        kind: Attribute
        cardinality: one
        optional: false
        identifier: "devicetype__devices"
        order_weight: 900
      - name: rack
        peer: LocationRack
        kind: Attribute
        cardinality: one
        optional: false
        identifier: "rack__devices"
        order_weight: 950
      - name: tags
        peer: BuiltinTag
        cardinality: many
        kind: Attribute
        optional: true
        order_weight: 3000

  # Vendor-specific generic with computed attributes
  - name: GenericDellDevice
    namespace: Dcim
    description: Dell-specific device attributes
    label: DellDevice
    icon: mdi:server
    include_in_menu: false
    attributes:
      - name: dell_asset_tag
        label: Dell Asset Tag
        kind: Text
        computed_attribute:
          kind: Jinja2
          jinja2_template: >-
            {% if asset_tag__value %}
            {{ asset_tag__value }}
            {% else %}N/A{% endif %}
        optional: false
        read_only: true
        order_weight: 2100

nodes:
  # Device Type (standalone, not inheriting)
  - name: DeviceType
    namespace: Dcim
    description: A model/type of device
    label: Device Type
    icon: mdi:devices
    include_in_menu: false
    human_friendly_id:
      - "model__value"
    order_by:
      - model__value
    display_label: "{{ manufacturer__name__value }} {{ model__value }}"
    attributes:
      - name: model
        kind: Text
        unique: true
        order_weight: 1000
      - name: u_height
        label: Height (U)
        kind: Number
        default_value: 1
        order_weight: 1300
      - name: is_full_depth
        label: Full Depth
        kind: Boolean
        default_value: true
        order_weight: 1400
    relationships:
      - name: manufacturer
        peer: OrganizationManufacturer
        kind: Attribute
        cardinality: one
        optional: false
        identifier: "manufacturer__device_types"
        order_weight: 900

  # Multiple inheritance: GenericDevice + GenericDellDevice
  - name: DellServer
    namespace: Dcim
    include_in_menu: false
    inherit_from:
      - DcimGenericDevice
      - DcimGenericDellDevice      # Gets dell_asset_tag computed attribute

  # Simple inheritance nodes
  - name: Switch
    namespace: Dcim
    description: Network Switch
    icon: mdi:switch
    include_in_menu: false
    inherit_from:
      - DcimGenericDevice

  - name: Router
    namespace: Dcim
    description: Network Router
    icon: mdi:router-network
    include_in_menu: false
    inherit_from:
      - DcimGenericDevice

  - name: UPS
    namespace: Dcim
    description: Uninterruptible Power Supply
    icon: mdi:battery-charging
    include_in_menu: false
    inherit_from:
      - DcimGenericDevice
```

**Key patterns:**

- `GenericDevice` defines all shared device attributes
- `GenericDellDevice` adds vendor-specific computed attributes
- `DellServer` uses **multiple inheritance** to combine both generics
- Simple devices (`Switch`, `Router`, `UPS`) inherit only from `GenericDevice`
- `DeviceType` is a standalone node (not a device itself)
- `display_label` uses Jinja2 to combine manufacturer + model

---

## Component Pattern (Modules/Slots)

Parent-child ownership with Component/Parent relationships.

```yaml
nodes:
  # Module type definition
  - name: ModuleType
    namespace: Dcim
    description: A type of installable module
    icon: mdi:expansion-card
    include_in_menu: false
    human_friendly_id:
      - "model__value"
    attributes:
      - name: model
        kind: Text
        unique: true
        order_weight: 1000
      - name: module_category
        kind: Dropdown
        order_weight: 1150
        choices:
          - name: psu
            label: Power Supply
          - name: gpu
            label: GPU
          - name: nic
            label: Network Interface Card
    relationships:
      - name: manufacturer
        peer: OrganizationManufacturer
        kind: Attribute
        cardinality: one
        optional: false
        identifier: "manufacturer__module_types"
        order_weight: 900

  # Module bay template (slot definition on a device type)
  - name: ModuleBayTemplate
    namespace: Dcim
    description: Slot for installing modules
    icon: mdi:slot-machine
    include_in_menu: false
    human_friendly_id:
      - "device_type__model__value"
      - "name__value"
    uniqueness_constraints:
      - ["device_type", "name__value"]   # Unique bay name per device type
    attributes:
      - name: name
        kind: Text
        order_weight: 1000
      - name: bay_type
        kind: Dropdown
        order_weight: 1150
        choices:
          - name: psu
            label: Power Supply
          - name: pcie
            label: PCIe Slot
    relationships:
      - name: device_type
        peer: DcimDeviceType
        kind: Parent                     # Bay belongs to a DeviceType
        cardinality: one
        optional: false
        identifier: "devicetype__module_bay_templates"

  # Module installation (tracks which module is in which slot)
  - name: ModuleInstallation
    namespace: Dcim
    description: Module installed in a device bay
    icon: mdi:expansion-card-variant
    include_in_menu: false
    human_friendly_id:
      - "device__name__value"
      - "slot_name__value"
    display_label: "{{ device__name__value }} / {{ slot_name__value }}"
    uniqueness_constraints:
      - ["device", "slot_name__value"]   # One module per slot per device
    attributes:
      - name: slot_name
        kind: Text
        order_weight: 1000
      - name: status
        kind: Dropdown
        default_value: active
        order_weight: 1100
        choices:
          - name: active
            label: Active
            color: "#00FF00"
          - name: empty
            label: Empty
            color: "#808080"
    relationships:
      - name: device
        peer: DcimGenericDevice
        kind: Parent                     # Installation belongs to a Device
        cardinality: one
        optional: false
        identifier: "device__modules"
        order_weight: 900
      - name: bay
        peer: DcimModuleBayTemplate
        kind: Attribute
        cardinality: one
        optional: false
        identifier: "modulebay__installations"
        order_weight: 920
      - name: module_type
        peer: DcimModuleType
        kind: Attribute
        cardinality: one
        optional: true                   # Empty if slot is vacant
        identifier: "moduletype__installations"
        order_weight: 950
```

**Key patterns:**

- `ModuleBayTemplate` -> `DeviceType` via Parent/Component
- `ModuleInstallation` -> `Device` via Parent/Component
- `uniqueness_constraints` ensure one module per slot per device
- `display_label` combines device name + slot name with Jinja2

---

## IPAM Schema (Inheriting Built-in Types)

IP address management inheriting from Infrahub built-in types.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

nodes:
  - name: IPAddress
    namespace: Ipam
    description: IP Address
    label: IP Address
    icon: mdi:ip
    include_in_menu: false
    inherit_from:
      - BuiltinIPAddress           # Built-in type provides address field
    order_by:
      - address__value
    display_label: address__value
    uniqueness_constraints:
      - [address__value, ip_namespace]
    human_friendly_id:
      - address__value
      - ip_namespace__name__value
    attributes:
      - name: fqdn
        label: FQDN
        kind: Text
        optional: true
        parameters:
          regex: "(?=^.{1,253}$)(^(((?!-)[a-zA-Z0-9-]{1,63}(?<!-))|((?!-)[a-zA-Z0-9-]{1,63}(?<!-)\.)+[a-zA-Z]{2,63})$)"
    relationships:
      - name: interface
        peer: InterfaceLayer3
        optional: true
        cardinality: one

  - name: Prefix
    namespace: Ipam
    description: IPv4 or IPv6 network
    icon: mdi:ip-network
    include_in_menu: false
    inherit_from:
      - BuiltinIPPrefix            # Built-in type provides prefix field
    order_by:
      - prefix__value
    display_label: prefix__value
    uniqueness_constraints:
      - [prefix__value, ip_namespace]
    human_friendly_id:
      - prefix__value
      - ip_namespace__name__value
    attributes:
      - name: status
        kind: Dropdown
        choices:
          - name: active
            label: Active
          - name: deprecated
            label: Deprecated
          - name: reserved
            label: Reserved
    relationships:
      - name: organization
        peer: OrganizationGeneric
        optional: true
        cardinality: one
        kind: Attribute
        order_weight: 1200
      - name: gateway
        label: L3 Gateway
        identifier: prefix__gateway    # Identifier for same-type relationship
        peer: IpamIPAddress
        optional: true
        cardinality: one
        kind: Attribute
        order_weight: 1500
```

**Key patterns:**

- Inherits from `BuiltinIPAddress` / `BuiltinIPPrefix`
  (provides address/prefix fields)
- `regex` validation on FQDN attribute
- `identifier` on gateway relationship (same peer type as other IP relationships)
- `uniqueness_constraints` combines attribute with namespace relationship

---

## Extensions Pattern (Cross-File Relationships)

Adding relationships between nodes defined in different schema files.

```yaml
---
# yaml-language-server: $schema=https://schema.infrahub.app/infrahub/schema/latest.json
version: "1.0"

# Define new nodes
nodes:
  - name: VLAN
    namespace: Ipam
    description: Isolated layer two domain
    icon: mdi:lan-pending
    menu_placement: IpamL2Domain
    uniqueness_constraints:
      - [vlan_id__value, l2domain]
    human_friendly_id:
      - name__value
    attributes:
      - name: name
        kind: Text
      - name: vlan_id
        kind: Number
      - name: status
        kind: Dropdown
        choices:
          - name: active
            label: Active
            color: "#7fbf7f"
    relationships:
      - name: l2domain
        peer: IpamL2Domain
        optional: false
        cardinality: one
        kind: Attribute
        order_weight: 1200

# Extend EXISTING nodes from other schema files
extensions:
  nodes:
    - kind: IpamPrefix             # Add VLAN relationship to Prefix
      relationships:
        - name: vlan
          peer: IpamVLAN
          optional: true
          cardinality: one
          kind: Attribute
          order_weight: 1400

    - kind: InterfaceLayer2        # Add VLAN relationships to L2 interfaces
      relationships:
        - name: untagged_vlan
          label: Untagged VLAN
          peer: IpamVLAN
          optional: true
          cardinality: one
          kind: Generic
          identifier: interface_l2__untagged_vlan
        - name: tagged_vlan
          label: Tagged VLANs
          peer: IpamVLAN
          optional: true
          cardinality: many
          kind: Generic
          identifier: interface_l2__tagged_vlan
```

**Key patterns:**

- `extensions.nodes` adds to existing nodes without modifying their schema file
- Each extension references existing node by `kind`
- New relationships/attributes are added to the existing node's definition
- Keeps schemas modular -- each file can focus on its domain

---

## Network Interface Schema (Multiple Generics Composing Behavior)

Advanced pattern showing interface composition with multiple generics.

```yaml
generics:
  # Base interface
  - name: Interface
    namespace: Dcim
    description: Generic Network Interface
    include_in_menu: false
    display_label: name__value
    order_by: [device__name__value, name__value]
    uniqueness_constraints:
      - [device, name__value]
    human_friendly_id:
      - device__name__value
      - name__value
    attributes:
      - name: name
        kind: Text
        order_weight: 1000
      - name: mtu
        label: MTU
        kind: Number
        default_value: 1514
        order_weight: 1300
      - name: status
        kind: Dropdown
        default_value: active
        order_weight: 1200
        choices:
          - name: active
            label: Active
            color: "#A9CCE3"
          - name: disabled
            label: Disabled
            color: "#D3D3D3"
    relationships:
      - name: device
        peer: DcimGenericDevice
        identifier: device__interface
        kind: Parent
        cardinality: one
        optional: false
        order_weight: 1025

  # Layer 2 mixin
  - name: Layer2
    namespace: Interface
    include_in_menu: false
    attributes:
      - name: l2_mode
        label: Layer2 Mode
        kind: Dropdown
        optional: true
        order_weight: 1500
        choices:
          - name: access
            label: Access
          - name: trunk
            label: Trunk

  # Layer 3 mixin
  - name: Layer3
    namespace: Interface
    include_in_menu: false
    attributes:
      - name: mac_address
        kind: Text
        optional: true
        order_weight: 1550
    relationships:
      - name: ip_addresses
        peer: IpamIPAddress
        cardinality: many
        kind: Attribute
        optional: true
        order_weight: 1150

nodes:
  # Physical interface: compose all three generics
  - name: Physical
    namespace: Interface
    label: Physical Interface
    description: Physical network port
    inherit_from:
      - DcimInterface
      - InterfaceLayer2
      - InterfaceLayer3
    include_in_menu: false

  # Virtual interface: L2 + L3 but no physical endpoint
  - name: Virtual
    namespace: Interface
    label: Virtual Interface
    description: Virtual interface (VLAN, Loopback)
    inherit_from:
      - DcimInterface
      - InterfaceLayer2
      - InterfaceLayer3
    include_in_menu: false
```

**Key patterns:**

- Separate generics for L2 and L3 behavior (composition over inheritance)
- Physical interfaces combine all three generics
- Virtual interfaces can selectively include/exclude generics
- `identifier` on device relationship matches the Component side on GenericDevice

---

## Custom Menu File

Full custom menu with nested groups.

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceManagementMenu
      label: Device Management
      icon: "mdi:server"
      children:
        data:
          - namespace: Dcim
            name: DevicesMenu
            label: Infrastructure
            icon: "mdi:server"
            children:
              data:
                - namespace: Dcim
                  name: DellServers
                  label: Dell Servers
                  kind: DcimDellServer
                  icon: mdi:server
                - namespace: Dcim
                  name: Switches
                  label: Switches
                  kind: DcimSwitch
                  icon: mdi:switch
          - namespace: Dcim
            name: TypesMenu
            label: Types & Platforms
            icon: "mdi:cog"
            children:
              data:
                - namespace: Organization
                  name: Manufacturers
                  label: Manufacturers
                  kind: OrganizationManufacturer
                  icon: "mdi:factory"
                - namespace: Dcim
                  name: DeviceTypes
                  label: Device Types
                  kind: DcimDeviceType
                  icon: "mdi:package-variant"

    - namespace: Location
      name: LocationsMenu
      label: Locations
      icon: "mdi:map-marker"
      children:
        data:
          - namespace: Location
            name: Regions
            label: Regions
            kind: LocationRegion
            icon: "mdi:earth"
          - namespace: Location
            name: Sites
            label: Sites
            kind: LocationSite
            icon: "mdi:office-building"
          - namespace: Location
            name: Racks
            label: Racks
            kind: LocationRack
            icon: "mdi:server"
```

---

## State Management (Removing Attributes)

Use `state: absent` to remove attributes during schema migration:

```yaml
nodes:
  - name: ModuleInstallation
    namespace: Dcim
    attributes:
      - name: old_field_name
        kind: Text
        state: absent              # This attribute will be removed
      - name: new_field_name
        kind: Text
        order_weight: 1000         # Replacement attribute
```
