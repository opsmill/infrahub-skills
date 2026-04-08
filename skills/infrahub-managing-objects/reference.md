# Infrahub Object File Reference

## Document Structure

```yaml
---
# Required. Always this value.
apiVersion: infrahub.app/v1
# Optional. Version string.
version: "1.0"
# Required. Always "Object" for data files.
kind: Object
spec:
  # Required. Schema node kind (e.g., DcimDellServer).
  kind: <NodeKind>
  # Required. List of object instances.
  data:
    - <field>: <value>
```

## Value Types by Schema Attribute Kind

| Schema Attribute Kind | YAML Value Type | Example |
| --- | --- | --- |
| `Text` | string | `name: "My Device"` |
| `TextArea` | string (multiline ok) | `description: "Long text"` |
| `Number` | integer | `rack_u_position: 33` |
| `Boolean` | boolean | `is_full_depth: true` |
| `Dropdown` | string (choice `name`) | `status: active` |
| `DateTime` | string (ISO format) | `created: "2024-01-15T10:30:00Z"` |
| `IPHost` | string | `address: "192.168.1.1/24"` |
| `IPNetwork` | string | `prefix: "10.0.0.0/8"` |
| `MacAddress` | string | `mac: "00:1A:2B:3C:4D:5E"` |
| `Email` | string | `email: "admin@example.com"` |
| `URL` | string | `website: "https://example.com"` |
| `JSON` | object/string | `config: {"key": "value"}` |
| `Password` | string | `password: "secret"` |

## Relationship Value Formats

### cardinality: one (Simple Reference)

Reference the target object by its `human_friendly_id`:

```yaml
# Target has human_friendly_id: [name__value]
manufacturer: Dell

# Target has human_friendly_id: [model__value]
device_type: PowerEdge R960

# Target has human_friendly_id:
#   [parent__shortname__value, name__value]
rack: ["room-shortname", "rack-name"]

# Target has human_friendly_id:
#   [manufacturer__name__value, name__value]
platform: [Juniper, JunOS]
```

**Rule**: Single-element `human_friendly_id` = scalar
value. Multi-element = list of values.

### cardinality: many (Inline Data)

For Component children or nested relationships:

```yaml
# Simple component children
tenants:
  data:
    - name: "Tenant A"
    - name: "Tenant B"

# Component children with specified kind
interfaces:
  kind: InterfacePhysical
  data:
    - name: eth0
      status: active

# Hierarchical children (location trees)
children:
  kind: LocationSite
  data:
    - name: "Boston"
      shortname: "bos"
```

### cardinality: many (Group Membership)

```yaml
member_of_groups:
  - group_name_1
  - group_name_2
```

## Generic Relationship References

When a relationship targets a generic type (e.g.,
`LocationGeneric`) that does **not** have a
`human_friendly_id` defined, the standard scalar or
list HFID reference will fail. Use an inline data
block with an explicit `kind:` to specify the concrete
type instead:

```yaml
# FAILS — LocationGeneric has no HFID
location: "Acacias"

# WORKS — concrete kind with upsert
location:
  kind: LocationSite
  data:
    - name: "Acacias"
```

`infrahubctl object load` uses `allow_upsert=True`,
so the inline block finds the existing object by the
concrete type's HFID (no duplicate created).

Different objects can reference different concrete
types through the same generic relationship:

```yaml
data:
  # Site reference
  - prefix: "10.0.0.0/24"
    location:
      kind: LocationSite
      data:
        - name: "Acacias"
  # Building reference
  - prefix: "10.1.0.0/24"
    location:
      kind: LocationBuilding
      data:
        - name: "Building H"
```

**Rule**: Always specify `kind:` when the relationship
targets a generic type. Use only the fields needed to
match the concrete type's `human_friendly_id`.

## Inline Children Block Structure

When nesting children inline:

```yaml
<relationship_name>:
  # Required when multiple child types possible
  kind: <ChildNodeKind>
  # Optional
  parameters:
    # Enable interface range expansion
    expand_range: true
  data:
    - <child_field>: <value>
```

| Field | Required | Description |
| --- | --- | --- |
| `kind` | Sometimes | Child node kind. Required for hierarchy/Generic. |
| `parameters` | No | Processing parameters (e.g., `expand_range`) |
| `data` | Yes | List of child object instances |

## Interface Range Expansion

When `expand_range: true` is set in parameters,
interface names with `[N-M]` syntax are expanded:

```yaml
interfaces:
  kind: InterfacePhysical
  parameters:
    expand_range: true
  data:
    # Creates Ethernet1/1 through Ethernet1/4
    - name: Ethernet1/[1-4]
      role: customer
      status: active
    # Creates et-0/0/0 through et-0/0/3
    - name: et-0/0/[0-3]
      role: leaf
      status: active
```

All attributes on the template entry are copied to
each expanded interface.

## Special Object Types

### CoreRepository (Git Integration)

```yaml
spec:
  kind: CoreRepository
  data:
    - name: my-repo
      # Git remote URL or path
      location: "/upstream"
      default_branch: "main"
```

### CoreStandardGroup

```yaml
spec:
  kind: CoreStandardGroup
  data:
    - name: leafs
      description: All leaf switches
```

## File Loading Behavior

- Files in the `objects/` directory (as specified in
  `.infrahub.yml`) are loaded recursively
- Files are sorted by filename within each directory
- Use numeric prefixes (`01_`, `02_`) to control
  load order
- Multiple YAML documents per file (separated by
  `---`) are processed in order
- Subdirectories are processed alphabetically

## Dependency Resolution

Objects reference each other by `human_friendly_id`.
The referenced object must exist (or be defined
earlier in the same batch) when the referencing
object is loaded.

**Dependency chain example:**

```text
Manufacturers (no deps)
  -> Device Types (depend on Manufacturers)
    -> Module Bay Templates (depend on Device Types)
Locations (hierarchy, self-contained)
  -> Devices (depend on Device Types + Locations)
    -> Module Installations
       (depend on Devices + Bay Templates
        + Module Types)
```

## Matching human_friendly_id

To reference a target object, you need to know its
`human_friendly_id` from the schema:

**Single-element** (`human_friendly_id` has one field):

| Node | Field | Example |
| --- | --- | --- |
| `OrganizationManufacturer` | `name__value` | `manufacturer: Dell` |
| `DcimDeviceType` | `model__value` | `device_type: R960` |
| `DcimModuleType` | `model__value` | `module_type: Dell-KRT01` |
| `DcimGenericDevice` | `name__value` | `device: my-server-01` |
| `OrganizationTenant` | `name__value` | `tenant: Engineering` |

**Multi-element** (`human_friendly_id` has two
fields -- use a list):

| Node | Fields | Example |
| --- | --- | --- |
| `LocationRack` | parent shortname, name | `rack: ["rm", "Rack-A"]` |
| `LocationRoom` | parent name, name | (hierarchical nesting) |
| `DcimModuleBayTemplate` | device_type model, name | `bay: ["R960", "PSU1"]` |
| `DcimPlatform` | manufacturer name, name | `platform: [Juniper, JunOS]` |
