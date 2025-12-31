# Schema Examples

Ready-to-use Infrahub schema templates and patterns.

## Basic Node with Attributes

A simple node with various attribute types:

```yaml
---
version: "1.0"
nodes:
  - name: Device
    namespace: Network
    label: Network Device
    icon: mdi:server
    description: A network device such as router, switch, or firewall
    human_friendly_id:
      - "hostname__value"
    attributes:
      - name: hostname
        kind: Text
        unique: true
        description: Unique hostname identifier
      - name: model
        kind: Text
        optional: true
      - name: serial_number
        kind: Text
        optional: true
      - name: status
        kind: Dropdown
        choices:
          - name: active
            color: "#00FF00"
          - name: maintenance
            color: "#FFA500"
          - name: decommissioned
            color: "#FF0000"
        default_value: active
```

## Attributes with Parameters

Attributes that support validation parameters (`Number`, `NumberPool`, `Text`, `TextArea`):

```yaml
---
version: "1.0"
nodes:
  - name: Server
    namespace: Infrastructure
    human_friendly_id:
      - "hostname__value"
    attributes:
      - name: hostname
        kind: Text
        unique: true
        parameters:
          regex: "^[a-z][a-z0-9-]+$"
          min_length: 3
          max_length: 63
      - name: rack_position
        kind: Number
        parameters:
          min_value: 1
          max_value: 48
      - name: cpu_cores
        kind: Number
        parameters:
          min_value: 1
          excluded_values: [13]
      - name: description
        kind: TextArea
        optional: true
        parameters:
          max_length: 1000
```

## Node with Relationships

Parent-child relationship between Device and Interface:

```yaml
---
version: "1.0"
nodes:
  - name: Device
    namespace: Network
    human_friendly_id:
      - "hostname__value"
    attributes:
      - name: hostname
        kind: Text
        unique: true
    relationships:
      - name: site
        peer: OrganizationSite
        kind: Attribute
        cardinality: one
        optional: true
        identifier: "site__devices"
      - name: interfaces
        peer: NetworkInterface
        kind: Component
        cardinality: many
        identifier: "device__interfaces"

  - name: Interface
    namespace: Network
    human_friendly_id:
      - "device__hostname__value"
      - "name__value"
    attributes:
      - name: name
        kind: Text
      - name: description
        kind: Text
        optional: true
      - name: mtu
        kind: Number
        default_value: 1500
      - name: enabled
        kind: Boolean
        default_value: true
    relationships:
      - name: device
        peer: NetworkDevice
        kind: Parent
        cardinality: one
        optional: false
        identifier: "device__interfaces"
```

## Generic with Inheritance

Base interface generic with specialized implementations:

```yaml
---
version: "1.0"
generics:
  - name: Interface
    namespace: Network
    description: Base interface generic
    human_friendly_id:
      - "device__hostname__value"
      - "name__value"
    attributes:
      - name: name
        kind: Text
      - name: description
        kind: Text
        optional: true
      - name: enabled
        kind: Boolean
        default_value: true
    relationships:
      - name: device
        peer: NetworkDevice
        kind: Parent
        cardinality: one
        optional: false

nodes:
  - name: PhysicalInterface
    namespace: Network
    inherit_from:
      - NetworkInterface
    icon: mdi:ethernet
    attributes:
      - name: speed
        kind: Bandwidth
        optional: true
      - name: mac_address
        kind: MacAddress
        optional: true

  - name: LogicalInterface
    namespace: Network
    inherit_from:
      - NetworkInterface
    icon: mdi:lan
    attributes:
      - name: vlan_id
        kind: Number
        optional: true
```

## Complete Infrastructure Schema

Full example with locations, devices, and interfaces:

```yaml
---
version: "1.0"
generics:
  - name: Generic
    namespace: Location
    description: Base location type
    icon: mdi:map-marker
    attributes:
      - name: name
        kind: Text
        unique: true
      - name: description
        kind: Text
        optional: true

nodes:
  - name: Site
    namespace: Organization
    inherit_from:
      - LocationGeneric
    icon: mdi:office-building
    human_friendly_id:
      - "name__value"
    attributes:
      - name: address
        kind: TextArea
        optional: true
      - name: site_type
        kind: Dropdown
        choices:
          - name: datacenter
          - name: office
          - name: remote
    relationships:
      - name: devices
        peer: NetworkDevice
        kind: Component
        cardinality: many
        identifier: "site__devices"

  - name: Device
    namespace: Network
    icon: mdi:server-network
    human_friendly_id:
      - "hostname__value"
    attributes:
      - name: hostname
        kind: Text
        unique: true
      - name: management_ip
        kind: IPHost
        optional: true
      - name: platform
        kind: Text
        optional: true
    relationships:
      - name: site
        peer: OrganizationSite
        kind: Parent
        cardinality: one
        optional: false
        identifier: "site__devices"
      - name: interfaces
        peer: NetworkInterface
        kind: Component
        cardinality: many
        identifier: "device__interfaces"

  - name: Interface
    namespace: Network
    icon: mdi:ethernet
    human_friendly_id:
      - "device__hostname__value"
      - "name__value"
    attributes:
      - name: name
        kind: Text
      - name: ip_address
        kind: IPHost
        optional: true
      - name: enabled
        kind: Boolean
        default_value: true
    relationships:
      - name: device
        peer: NetworkDevice
        kind: Parent
        cardinality: one
        optional: false
        identifier: "device__interfaces"
```

## IP Address Management (IPAM) Schema

Schema for managing IP prefixes and addresses:

```yaml
---
version: "1.0"
nodes:
  - name: Prefix
    namespace: Ipam
    icon: mdi:ip-network
    human_friendly_id:
      - "prefix__value"
    attributes:
      - name: prefix
        kind: IPNetwork
        unique: true
      - name: description
        kind: Text
        optional: true
      - name: status
        kind: Dropdown
        choices:
          - name: active
          - name: reserved
          - name: deprecated
        default_value: active
    relationships:
      - name: parent
        peer: IpamPrefix
        kind: Parent
        cardinality: one
        optional: true
        identifier: "prefix__children"
      - name: children
        peer: IpamPrefix
        kind: Component
        cardinality: many
        identifier: "prefix__children"
      - name: addresses
        peer: IpamAddress
        kind: Component
        cardinality: many
        identifier: "prefix__addresses"

  - name: Address
    namespace: Ipam
    icon: mdi:ip
    human_friendly_id:
      - "address__value"
    attributes:
      - name: address
        kind: IPHost
        unique: true
      - name: description
        kind: Text
        optional: true
    relationships:
      - name: prefix
        peer: IpamPrefix
        kind: Parent
        cardinality: one
        optional: true
        identifier: "prefix__addresses"
      - name: interface
        peer: NetworkInterface
        kind: Attribute
        cardinality: one
        optional: true
        identifier: "interface__addresses"
```

## VLAN Management Schema

Schema for VLAN and VLAN group management:

```yaml
---
version: "1.0"
nodes:
  - name: VlanGroup
    namespace: Network
    icon: mdi:folder-network
    human_friendly_id:
      - "name__value"
    attributes:
      - name: name
        kind: Text
        unique: true
      - name: description
        kind: Text
        optional: true
    relationships:
      - name: vlans
        peer: NetworkVlan
        kind: Component
        cardinality: many
        identifier: "vlangroup__vlans"

  - name: Vlan
    namespace: Network
    icon: mdi:lan
    human_friendly_id:
      - "group__name__value"
      - "vlan_id__value"
    uniqueness_constraints:
      - ["group", "vlan_id"]
    attributes:
      - name: vlan_id
        kind: Number
        parameters:
          min_value: 1
          max_value: 4094
      - name: name
        kind: Text
      - name: description
        kind: Text
        optional: true
      - name: status
        kind: Dropdown
        choices:
          - name: active
          - name: reserved
          - name: deprecated
        default_value: active
    relationships:
      - name: group
        peer: NetworkVlanGroup
        kind: Parent
        cardinality: one
        optional: false
        identifier: "vlangroup__vlans"
```

## Rack and Location Schema

Schema for physical infrastructure locations:

```yaml
---
version: "1.0"
generics:
  - name: Location
    namespace: Dcim
    description: Physical location
    hierarchical: true
    attributes:
      - name: name
        kind: Text
      - name: description
        kind: Text
        optional: true

nodes:
  - name: Region
    namespace: Dcim
    inherit_from:
      - DcimLocation
    icon: mdi:earth
    human_friendly_id:
      - "name__value"
    attributes:
      - name: name
        kind: Text
        unique: true

  - name: Site
    namespace: Dcim
    inherit_from:
      - DcimLocation
    icon: mdi:office-building
    human_friendly_id:
      - "name__value"
    attributes:
      - name: name
        kind: Text
        unique: true
      - name: address
        kind: TextArea
        optional: true
      - name: latitude
        kind: Number
        optional: true
      - name: longitude
        kind: Number
        optional: true

  - name: Room
    namespace: Dcim
    inherit_from:
      - DcimLocation
    icon: mdi:door
    human_friendly_id:
      - "site__name__value"
      - "name__value"

  - name: Rack
    namespace: Dcim
    icon: mdi:server
    human_friendly_id:
      - "room__name__value"
      - "name__value"
    attributes:
      - name: name
        kind: Text
      - name: height
        kind: Number
        default_value: 42
        description: Rack height in U
      - name: description
        kind: Text
        optional: true
    relationships:
      - name: room
        peer: DcimRoom
        kind: Parent
        cardinality: one
        optional: false
        identifier: "room__racks"
```
