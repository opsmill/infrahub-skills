# Infrahub Object File Examples

Real-world examples extracted from production Infrahub repositories.

---

## 1. Simple Flat List (Manufacturers)

The simplest pattern -- attributes only, no relationships.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationManufacturer
  data:
    - name: Acopian
    - name: Chatsworth Products
    - name: Dell
    - name: Intel
    - name: Juniper
    - name: Nvidia
    - name: Supermicro
```

**Key points:**

- No relationships, so each item is just a `name`
  attribute
- Load order: these have no dependencies, so they
  go first (prefix `01_`)

---

## 2. Parent-Child Inline (Tenant Groups with Tenants)

Component/Parent relationships use inline `data` blocks.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationTenantGroup
  data:
    - name: Quera-Internal
      tenants:
        data:
          - name: Test and Engineering Infrastructure
          - name: IT
          - name: M4A
          - name: M4B
          - name: Castor
    - name: External-Customers
      tenants:
        data:
          - name: AIST
```

**Key points:**

- `tenants` is a Component relationship on
  TenantGroup
- Children are nested inline under `data:` (no
  `kind` needed since only one type of tenant
  exists)
- The parent and all its children are created
  atomically

---

## 3. Groups (CoreStandardGroup)

Groups are standalone objects that devices reference
via `member_of_groups`.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreStandardGroup
  data:
    - name: edge_routers
      description: Edge Routers
    - name: leafs
      description: All leaf switches
    - name: spines
      description: All spine switches
    - name: firewalls
      description: All firewalls
    - name: linux_devices
      description: Linux Devices
```

**Key points:**

- Groups should be created early (before devices
  that reference them)
- Devices reference groups via `member_of_groups`
  list

---

## 4. Device Types (Referencing Manufacturers)

Device types reference manufacturers by
`human_friendly_id` (which is `name` for
manufacturers).

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDeviceType
  data:
    # PDUs
    - model: EA-5007
      manufacturer: Chatsworth Products
      part_number: EA-5007-C / EA-5007-E / EA-5007-CE
      role: PDU
      airflow: passive
      weight: 18
      weight_unit: lb
      description: "8.6kW Switched PDU with 24x C13 outlets."

    # Servers
    - model: PowerEdge R660xs
      manufacturer: Dell
      part_number: R660xs
      u_height: 1
      is_full_depth: true
      airflow: front-to-rear

    - model: PowerEdge R960
      manufacturer: Dell
      part_number: R960
      u_height: 4
      is_full_depth: true
      airflow: front-to-rear
      description: "4u 12x Gen5 PCIe server"

    # Switches
    - model: EX4100-48MP
      manufacturer: Juniper
      part_number: EX4100-48MP
      u_height: 1
      is_full_depth: false
      airflow: front-to-rear
```

**Key points:**

- `manufacturer: Dell` references
  `OrganizationManufacturer` by its
  `human_friendly_id` (`[name__value]`)
- Dropdown values use `name` not `label`:
  `airflow: front-to-rear` (not "Front to Rear")
- Manufacturers must be loaded before device types

---

## 5. Module Types

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimModuleType
  data:
    # PSU Modules
    - model: Dell-KRT01-800W
      manufacturer: Dell
      part_number: KRT01
      module_category: psu
      description: Dell 800W AC Titanium Hot-Plug PSU

    # GPU Modules
    - model: Nvidia-T1000
      manufacturer: Nvidia
      part_number: T1000
      module_category: gpu
      description: Nvidia T1000 PCIe 3.0 x16 GPU

    # NIC Modules (OCP)
    - model: Dell-E810-XXVDA4-OCP
      manufacturer: Dell
      part_number: Y4VV5
      module_category: nic
      description: Intel E810-XXVDA4 Quad Port 10/25GbE SFP28 Adapter, OCP NIC 3.0

    # NIC Modules (PCIe)
    - model: Intel-E810-2CQDA2
      manufacturer: Intel
      part_number: E810-2CQDA2
      module_category: nic
      description: 2x 100GbE QSFP28
```

**Key points:**

- `module_category` is a Dropdown -- use the choice
  `name` value
- `manufacturer` references by `human_friendly_id`

---

## 6. Module Bay Templates

Bay templates define available slots on a device
type. They reference device types by
`human_friendly_id` (which is `[model__value]`).

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimModuleBayTemplate
  data:
    # Dell PowerEdge R660xs PSU bays
    - name: PSU1
      device_type: PowerEdge R660xs
      bay_type: psu
      label: PSU1
      position: Left from Rear

    - name: PSU2
      device_type: PowerEdge R660xs
      bay_type: psu
      label: PSU2
      position: Right from Rear

    # Dell PowerEdge R660xs OCP slot
    - name: OCP Slot 1
      device_type: PowerEdge R660xs
      bay_type: ocp
      description: OCP 3.0 Slot PCIe Gen4 x16

    # Dell PowerEdge R660xs PCIe slots
    - name: PCIe Slot 1
      device_type: PowerEdge R660xs
      bay_type: pcie
      label: "1"
      description: Half-height / Low Profile (LP) PCIe Gen4 x16 slot

    - name: PCIe Slot 2
      device_type: PowerEdge R660xs
      bay_type: pcie
      label: "2"
      description: Half-height / Low Profile (LP) PCIe Gen5 x8 slot
```

**Key points:**

- `device_type: PowerEdge R660xs` references
  `DcimDeviceType` by model
- Bay templates must be created after device types
  but before module installations
- The `name` + `device_type` pair forms the
  `human_friendly_id` for this template

---

## 7. Hierarchical Location Tree

Locations nest inline from Region down to Rack,
specifying `kind` at each level.

```yaml
---
apiVersion: infrahub.app/v1
version: "1.0"
kind: Object
spec:
  kind: LocationRegion
  data:
    - name: "AMERICAS"
      shortname: "amer"
      description: "North and South America"
      children:
        kind: LocationSite
        data:
          - name: "1284 Soldier's Field Road"
            shortname: "sfr"
            description: "Main facility"
            address: |
              1284 Soldier's Field Road
              Boston, MA 02135
              United States
            timezone: "America/New_York"
            children:
              kind: LocationRoom
              data:
                - name: "01-4"
                  shortname: "01-4"
                  description: "Lab area 01-4"
                  children:
                    kind: LocationRack
                    data:
                      - name: "TEST-RACK1"
                        shortname: "test-rack1"
                        description: "Test rack in lab 01-4"
                        height: 42
                        width: 600
                        depth: 1200
```

**Key points:**

- `children.kind` is always required (specifies
  which hierarchical child type)
- The full tree is created atomically from one
  `spec` block
- `shortname` is critical -- it's used in
  `human_friendly_id` for rooms and racks
- Multiple regions can be defined as separate items
  in the top-level `data` list

### Deeper Location Hierarchy (bundle-dc pattern)

When schemas define more location levels
(Region > Country > Metro > Building):

```yaml
---
apiVersion: infrahub.app/v1
version: "1.0"
kind: Object
spec:
  kind: LocationRegion
  data:
    - name: "EMEA"
      shortname: "emea"
      children:
        kind: LocationCountry
        data:
          - name: "France"
            shortname: "fr"
            children:
              kind: LocationMetro
              data:
                - name: "Paris"
                  shortname: "par"
                  children:
                    kind: LocationBuilding
                    data:
                      - name: "PAR-1"
                        shortname: "par-1"
          - name: "Germany"
            shortname: "de"
            children:
              kind: LocationMetro
              data:
                - name: "Frankfurt"
                  shortname: "fra"
                  children:
                    kind: LocationBuilding
                    data:
                      - name: "FRA-1"
                        shortname: "fra-1"
```

---

## 8. Devices (With Type and Location References)

Devices reference device types and racks by
`human_friendly_id`.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDellServer
  data:
    - name: TEST-R660xs-1
      device_type: PowerEdge R660xs
      rack: ["01-4", "TEST-RACK1"]       # [room_shortname, rack_name]
      rack_u_position: 33
      rack_face: front
      status: active
      serial: "SN12345"
      warranty_expire_date: "2222-01-01"
      asset_tag: "1234567890"
      purchase_order: "[1234567890](https://app.bellwethercorp.com)"

    - name: TEST-R960-1
      device_type: PowerEdge R960
      rack: ["01-4", "TEST-RACK1"]
      rack_u_position: 23
      rack_face: front
      status: active
      serial: "qwertyuiop"
```

**Key points:**

- `device_type: PowerEdge R660xs` -- scalar because
  DcimDeviceType has single-element
  `human_friendly_id` (`[model__value]`)
- `rack: ["01-4", "TEST-RACK1"]` -- list because
  LocationRack has multi-element
  `human_friendly_id`
  (`[parent__shortname__value, name__value]`)
- `rack_face` and `status` are Dropdowns -- use
  the `name` value
- `warranty_expire_date` is a DateTime, formatted
  as ISO string

---

## 9. Multiple Document Types in One File

A single file can contain multiple YAML documents
(separated by `---`), each targeting a different
node kind.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDellServer
  data:
    - name: TEST-R660xs-1
      device_type: PowerEdge R660xs
      rack: ["01-4", "TEST-RACK1"]
      rack_u_position: 33
      rack_face: front
      status: active

---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimSwitch
  data:
    - name: TEST-SP-EX4100-48
      device_type: EX4100-48MP
      rack: ["south-pole", "TEST-SP-RACK"]
      rack_u_position: 42
      rack_face: front
      status: active
      serial: "SN12345789"

---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimPDU
  data:
    - name: TEST-CPI-5007-A
      device_type: EA-5007
      rack: ["01-4", "TEST-RACK1"]
      rack_face: rear
      status: active
      serial: "asdfghjkl"
      pdu_type: switched
```

**Key points:**

- Each `---` separated document has its own
  `apiVersion`, `kind`, and `spec`
- Each `spec.kind` targets exactly one node kind
- Documents are processed in order within the file

---

## 10. Devices with Inline Interfaces

Devices can include interfaces as inline Component
children.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: SecurityFirewall
  data:
    - name: corp-firewall
      role: edge_firewall
      device_type: SRX-1500
      platform: [Juniper, JunOS]          # Multi-element human_friendly_id
      location: PAR-1
      status: active
      member_of_groups:
        - juniper_firewall
      interfaces:
        kind: InterfacePhysical
        data:
          - name: fxp0
            role: management
            status: active
          - name: ge-0/0/0
            role: leaf
            status: active
          - name: ge-0/0/1
            role: leaf
            status: active
```

**Key points:**

- `platform: [Juniper, JunOS]` -- list because
  DcimPlatform has `human_friendly_id`:
  `[manufacturer__name__value, name__value]`
- `interfaces.kind: InterfacePhysical` -- required
  because the relationship peer may be a Generic
- `member_of_groups` -- simple list of group names

---

## 11. Devices with Interface Range Expansion

Use `expand_range: true` to auto-generate sequential
interfaces.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: cisco-switch-01
      role: leaf
      device_type: N9K-C93108TC-FX
      platform: [Cisco, NX-OS]
      location: LON-1
      status: active
      member_of_groups:
        - leafs
      interfaces:
        kind: InterfacePhysical
        parameters:
          expand_range: true
        data:
          - name: mgmt0
            role: management
            status: active
          - name: Ethernet1/[1-4]         # Expands to Ethernet1/1 through Ethernet1/4
            role: customer
            status: active

    - name: juniper-switch-01
      role: spine
      device_type: QFX5220-32CD
      platform: [Juniper, JunOS]
      location: FRA-1
      status: active
      interfaces:
        kind: InterfacePhysical
        parameters:
          expand_range: true
        data:
          - name: fxp0
            role: management
            status: active
          - name: et-0/0/[0-3]            # Expands to et-0/0/0 through et-0/0/3
            role: leaf
            status: active
```

**Key points:**

- `parameters.expand_range: true` goes on the
  relationship block, NOT on individual interfaces
- Range syntax: `[N-M]` in the interface name
- All attributes from the template entry are copied
  to each expanded interface
- Non-range interfaces (like `mgmt0`, `fxp0`) in
  the same block are not affected

---

## 12. Module Installations (Occupied Slots)

Module installations connect devices to module types
via bay templates.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimModuleInstallation
  data:
    # PSU installations
    - device: TEST-R660xs-1
      slot_name: PSU1
      bay:
        - PowerEdge R660xs              # device_type model
        - PSU1                           # bay name
      module_type: Dell-KRT01-800W       # References DcimModuleType by model
      status: active

    - device: TEST-R660xs-1
      slot_name: PSU2
      bay:
        - PowerEdge R660xs
        - PSU2
      module_type: Dell-KRT01-800W
      status: active

    # OCP NIC installation
    - device: TEST-R660xs-1
      slot_name: OCP Slot 1
      bay:
        - PowerEdge R660xs
        - OCP Slot 1
      module_type: Dell-E810-XXVDA4-OCP
      status: active

    # PCIe GPU installation
    - device: TEST-R660xs-1
      slot_name: PCIe Slot 1
      bay:
        - PowerEdge R660xs
        - PCIe Slot 1
      module_type: PNY-RTX4000-ADA-SFF
      status: active
```

**Key points:**

- `device: TEST-R660xs-1` -- references the device
  by name (`human_friendly_id: [name__value]`)
- `bay` is a list: `[device_type_model, bay_name]`
  matching `DcimModuleBayTemplate`'s
  `human_friendly_id`:
  `[device_type__model__value, name__value]`
- `module_type: Dell-KRT01-800W` -- references
  `DcimModuleType` by model
- Requires: devices, bay templates, and module
  types all loaded first

---

## 13. Empty/Vacant Slots

Track unoccupied module bays -- same structure as
installations but with `status: empty` and no
`module_type`.

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimModuleInstallation
  data:
    - device: TEST-R660xs-1
      slot_name: PCIe Slot 3
      bay:
        - PowerEdge R660xs
        - PCIe Slot 3
      status: empty                      # No module_type = vacant slot

    - device: TEST-R960-1
      slot_name: PSU1
      bay:
        - PowerEdge R960
        - PSU1
      status: empty

    - device: TEST-R960-1
      slot_name: OCP Slot 1
      bay:
        - PowerEdge R960
        - OCP Slot 1
      status: empty
```

**Key points:**

- No `module_type` field -- the slot is tracked
  as vacant
- Useful for inventory visibility: "which slots
  are available?"
- Typically in a separate file
  (e.g., `07_empty_slots.yml`) loaded after
  occupied installations

---

## 14. IP Prefixes

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: IpamPrefix
  data:
    - prefix: 10.0.0.0/8
      status: active
    - prefix: 10.10.0.0/16
      status: active
    - prefix: 172.16.0.0/16
      status: active
    - prefix: 192.168.0.0/16
      status: active
    - prefix: 192.168.1.0/24
      status: active
    - prefix: fd00:1000::/32
      status: active
```

**Key points:**

- IPv4 and IPv6 prefixes use the `IPNetwork`
  attribute kind
- CIDR notation is required

---

## 15. Git Repository

Special `CoreRepository` object for Infrahub's git
integration.

```yaml
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: CoreRepository
  data:
    - name: bundle-dc
      location: "/upstream"
      default_branch: "main"
```

**Key points:**

- `location` is the git remote URL or path
- Typically in a subdirectory like
  `objects/git-repo/`
- The `---` document separator is optional for
  the first document in a file

---

## Complete File Organization Example

```text
objects/
  01_manufacturers.yml
  02_organizations.yml
  03_device_types.yml
  04_module_types.yml
  04a_module_bay_templates.yml
  05_locations.yml
  06_devices.yml
  06_module_installations.yml
  07_empty_slots.yml
  git-repo/
    local-dev.yml
```

**Loading order:**

1. Files are sorted by filename within each
   directory
2. Subdirectories are processed alphabetically
   after files
3. Numeric prefixes (`01_`, `02_`) enforce correct
   dependency order
4. Use letter suffixes (`04a_`) to insert between
   existing numbers
