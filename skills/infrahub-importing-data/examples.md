# CSV Import — Worked Examples

Six realistic CSV inputs and the object YAML the
skill emits for each. Each example shows the input
CSV, the emitted YAML, and a short "why this
shape" note.

## Contents

- [1. Single Kind, Flat (Manufacturers)](#1-single-kind-flat-manufacturers)
- [2. Denormalized Sheet Split Across Kinds](#2-denormalized-sheet-split-across-kinds)
- [3. Parent With Repeated Children (Inline Components)](#3-parent-with-repeated-children-inline-components)
- [4. Dropdown Label Normalization](#4-dropdown-label-normalization)
- [5. Range Collapse (Interface Sequences)](#5-range-collapse-interface-sequences)
- [6. Lineage Stamping at Import](#6-lineage-stamping-at-import)

---

## 1. Single Kind, Flat (Manufacturers)

**Input:** `manufacturers.csv`

```csv
name,description,country
Dell,Server and storage vendor,US
Juniper,Network equipment,US
Arista,Network equipment,US
Cisco,Network equipment,US
```

**Schema:** `OrganizationManufacturer` with Text
attributes `name`, `description`, `country`;
`human_friendly_id: [name__value]`.

**Emission:** `output_dir/01_manufacturers.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationManufacturer
  data:
    - name: Dell
      description: Server and storage vendor
      country: US
    - name: Juniper
      description: Network equipment
      country: US
    - name: Arista
      description: Network equipment
      country: US
    - name: Cisco
      description: Network equipment
      country: US
```

**Why this shape:** No references; all columns map
to attributes by exact name match. The file gets the
`01_` prefix because manufacturers are referenced by
later files (device types, devices) and load order
matters at insert time — see
[../infrahub-managing-objects/rules/organization-load-order.md](../infrahub-managing-objects/rules/organization-load-order.md).

---

## 2. Denormalized Sheet Split Across Kinds

**Input:** `inventory.csv` — one big sheet
conflating manufacturer + location + device:

```csv
device_name,device_role,site_name,site_country,manufacturer_name,manufacturer_country
spine-01,spine,par-1,FR,Arista,US
spine-02,spine,par-1,FR,Arista,US
leaf-01,leaf,par-1,FR,Arista,US
edge-01,edge,nyc-1,US,Cisco,US
```

**Schema:** `OrganizationManufacturer`
(`hfid: [name__value]`), `LocationSite`
(`hfid: [name__value]`), `DcimDevice`
(`hfid: [name__value]`, relationships
`manufacturer` and `site`).

**Emission:** three numbered files.

`output_dir/01_manufacturers.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationManufacturer
  data:
    - name: Arista
      country: US
    - name: Cisco
      country: US
```

`output_dir/02_sites.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: LocationSite
  data:
    - name: par-1
      country: FR
    - name: nyc-1
      country: US
```

`output_dir/03_devices.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      role: spine
      site: par-1
      manufacturer: Arista
    - name: spine-02
      role: spine
      site: par-1
      manufacturer: Arista
    - name: leaf-01
      role: leaf
      site: par-1
      manufacturer: Arista
    - name: edge-01
      role: edge
      site: nyc-1
      manufacturer: Cisco
```

**Why this shape:** The detector saw that
`manufacturer_name` + `manufacturer_country` are
constant per group of rows (every Arista row shares
country `US`) and `site_name` + `site_country` are
constant per group. The interview confirmed the
split. Manufacturers and sites load first because
the device file references them by HFID; both
references are scalar strings because each target's
HFID is single-element.

---

## 3. Parent With Repeated Children (Inline Components)

**Input:** `devices_with_interfaces.csv` — device
columns repeat per interface:

```csv
device_name,device_role,interface_name,interface_role,interface_status
spine-01,spine,Ethernet1,uplink,active
spine-01,spine,Ethernet2,uplink,active
spine-01,spine,Ethernet3,server,active
leaf-01,leaf,Ethernet1,uplink,active
leaf-01,leaf,Ethernet2,server,active
```

**Schema:** `DcimDevice` has a Component
relationship `interfaces` whose peer is
`InterfacePhysical` (generic-typed), with the
matching Parent relationship on the child. See
[../infrahub-managing-objects/rules/children-components.md](../infrahub-managing-objects/rules/children-components.md).

**Emission:** `output_dir/03_devices.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      role: spine
      interfaces:
        kind: InterfacePhysical
        data:
          - name: Ethernet1
            role: uplink
            status: active
          - name: Ethernet2
            role: uplink
            status: active
          - name: Ethernet3
            role: server
            status: active
    - name: leaf-01
      role: leaf
      interfaces:
        kind: InterfacePhysical
        data:
          - name: Ethernet1
            role: uplink
            status: active
          - name: Ethernet2
            role: server
            status: active
```

**Why this shape:** Interfaces have no meaning
outside the device they belong to (Component
relationship), so they nest inline. `kind:
InterfacePhysical` is required on the wrapper
because the schema's `interfaces` relationship
points at a generic — without it the loader can't
pick a concrete schema and rejects the whole device
record. The interview confirmed inline components
over the separate-files alternative.

---

## 4. Dropdown Label Normalization

**Input:** `devices.csv` — `Status` column carries
display labels:

```csv
name,role,status
spine-01,spine,Active
spine-02,spine,Maintenance
leaf-01,leaf,Active
leaf-02,leaf,Retired
```

**Schema:** `DcimDevice.status` is a Dropdown with
choices:

```yaml
status:
  kind: Dropdown
  choices:
    - name: active
      label: Active
    - name: maintenance
      label: Maintenance
    - name: retired
      label: Retired
```

**Emission:** `output_dir/04_devices.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: spine-01
      role: spine
      status: active
    - name: spine-02
      role: spine
      status: maintenance
    - name: leaf-01
      role: leaf
      status: active
    - name: leaf-02
      role: leaf
      status: retired
```

**Why this shape:** The skill built a `label→name`
lookup from the schema's `choices` list and
translated each cell. Passing the label `"Active"`
straight through would be rejected at load time
with `'Active' is not a valid choice for status` —
see [../infrahub-managing-objects/rules/value-attributes.md](../infrahub-managing-objects/rules/value-attributes.md).

A cell that matched neither a `name` nor a `label`
(e.g., `status: "TBD"`) would have routed to the
interview rather than being silently dropped.

---

## 5. Range Collapse (Interface Sequences)

**Input:** `interfaces.csv` — 48 rows for one
device, contiguous interface names, all with the
same role/status:

```csv
device_name,interface_name,interface_role,interface_status
leaf-01,eth0,server,active
leaf-01,eth1,server,active
leaf-01,eth2,server,active
...
leaf-01,eth47,server,active
```

**Schema:** Same `DcimDevice` + `InterfacePhysical`
as example 3.

**Emission:** `output_dir/03_devices.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: DcimDevice
  data:
    - name: leaf-01
      interfaces:
        kind: InterfacePhysical
        parameters:
          expand_range: true
        data:
          - name: eth[0-47]
            role: server
            status: active
```

**Why this shape:** The detector saw 48 contiguous
interface names with identical sibling-column
values and collapsed them. The range is emitted
under `data:`; the `expand_range: true` directive
lives in `parameters:`, not on the individual data
item — placing it on the item is a no-op and
silently creates one interface named literally
`eth[0-47]`. See
[../infrahub-managing-objects/rules/range-expansion.md](../infrahub-managing-objects/rules/range-expansion.md).

If even one row varies (e.g., `eth17` has a
different role), the collapse doesn't apply for
that gap and the range either splits (`eth[0-16]`,
`eth17`, `eth[18-47]`) or falls back to
row-per-interface — confirm in the interview.

---

## 6. Lineage Stamping at Import

**Input:** Same `manufacturers.csv` as example 1.

**Interview decision:** stamp every imported value
with `source: csv-import-20260621-1430` so the
provenance shows up in the UI later.

**Prerequisite:** an `Account` (or `Repository`)
named `csv-import-20260621-1430` must already exist
on the target branch so the reference resolves at
load time. If it doesn't, the skill bootstraps the
account in a `00_lineage_accounts.yml` file ahead
of the data files.

**Emission:** `output_dir/01_manufacturers.yml`

```yaml
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: OrganizationManufacturer
  data:
    - name:
        value: Dell
        source: csv-import-20260621-1430
      description:
        value: Server and storage vendor
        source: csv-import-20260621-1430
      country:
        value: US
        source: csv-import-20260621-1430
    - name:
        value: Juniper
        source: csv-import-20260621-1430
      description:
        value: Network equipment
        source: csv-import-20260621-1430
      country:
        value: US
        source: csv-import-20260621-1430
```

**Why this shape:** Each attribute switches from
plain scalar to a `value` + metadata mapping. Only
the attributes you write as mappings carry
metadata; the rest stay plain.

**A common misconception worth surfacing in the
interview:** `source` is **lineage only**. It does
not lock the value or restrict who can edit it.
To actually lock imported data, the user needs to
set `owner: <group-name>` and `is_protected: true`
as well — see
[../infrahub-common/metadata-lineage.md](../infrahub-common/metadata-lineage.md).
Always confirm whether the user wants lineage only
or lineage + lock before emitting.
