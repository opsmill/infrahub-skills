# Infrahub Schema Property Reference

Complete reference for all schema properties. JSON Schema validation available at:
`https://schema.infrahub.app/infrahub/schema/latest.json`

## Top-Level Schema File

| Property | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `version` | string | **Yes** | - | Schema version, always `"1.0"` |
| `generics` | list | No | `[]` | List of GenericSchema definitions |
| `nodes` | list | No | `[]` | List of NodeSchema definitions |
| `extensions` | object | No | `{}` | SchemaExtension block for extending existing nodes |

---

## Node Properties

Properties for entries in the `nodes:` list. **Required: `name`, `namespace`.**

### Identity & Display

| Property | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `name` | string | *required* | 2-32 chars, `^[A-Z][a-zA-Z0-9]+$` | Node name (PascalCase) |
| `namespace` | string | *required* | 3-32 chars, `^[A-Z][a-z0-9]+$` | Namespace (first letter uppercase only) |
| `description` | string | null | Max 128 chars | Short description |
| `label` | string | null | Max 64 chars | Human-friendly display name (auto-generated if omitted) |
| `icon` | string | null | Valid Iconify value | Icon identifier (e.g., `mdi:server`, `mingcute:location-line`) |
| `display_label` | string | null | - | Attribute name or Jinja2 template (e.g., `"{{ manufacturer__name__value }} {{ name__value }}"`) |
| `human_friendly_id` | list[string] | null | - | Attribute/relationship paths forming human-readable ID (e.g., `["parent__name__value", "name__value"]`) |
| `order_by` | list[string] | null | - | Default sort order (e.g., `["name__value"]`) |

### Menu & Visibility

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `include_in_menu` | boolean | null | Whether to show in navigation menu |
| `menu_placement` | string | null | Kind of parent generic to group under in menu |
| `documentation` | string | null | URL to documentation |

### Inheritance & Hierarchy

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `inherit_from` | list[string] | `[]` | Generic kinds to inherit from (e.g., `["DcimGenericDevice"]`) |
| `parent` | string | null | Expected parent kind in hierarchy (set to `null` or `""` for root) |
| `children` | string | null | Expected child kind in hierarchy |
| `hierarchy` | string | null | Internal - hierarchy name (auto-set) |

### Constraints

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `uniqueness_constraints` | list[list[string]] | null | Multi-element uniqueness. Use `__value` for attributes, bare name for relationships. E.g., `[["rack", "name__value"]]` |
| `branch` | enum | `"aware"` | Branch support: `aware`, `agnostic`, `local` |

### Advanced

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `state` | enum | `"present"` | `present` or `absent` (for removing nodes) |
| `generate_profile` | boolean | `true` | Auto-generate a Profile schema |
| `generate_template` | boolean | `false` | Auto-generate a Template schema |

---

## Generic Properties

Generics use **all the same properties as nodes**, plus:

| Property | Type | Default | Description |
|----------|------|---------|-------------|
| `hierarchical` | boolean | `false` | Enable hierarchical mode (for location-style trees) |
| `used_by` | list[string] | `[]` | Internal - nodes referencing this generic |

**Generics do NOT have**: `inherit_from`, `parent`, `children`.

---

## Attribute Types

| Kind | Description | Special Properties |
|------|-------------|--------------------|
| `Text` | Standard text | `regex`, `min_length`, `max_length` (via `parameters`) |
| `TextArea` | Multi-line text | Same as Text |
| `Number` | Integer | `min_value`, `max_value`, `excluded_values` (via `parameters`) |
| `Boolean` | True/false | - |
| `Checkbox` | Boolean variant | - |
| `DateTime` | Date and time | - |
| `Dropdown` | Selection list | Requires `choices` |
| `IPHost` | IP host (e.g., 192.168.1.1/24) | - |
| `IPNetwork` | IP network (e.g., 192.168.0.0/24) | - |
| `MacAddress` | MAC address | - |
| `Email` | Email address | - |
| `URL` | URL | - |
| `Password` | Encrypted password | - |
| `HashedPassword` | Pre-hashed password | - |
| `JSON` | JSON data | - |
| `Any` | Any type | - |
| `List` | List of values | - |
| `File` | File reference | - |
| `Bandwidth` | Bandwidth value | - |
| `Color` | Hex color | - |

**Deprecated**: `String` (use `Text`), `NumberPool` (special internal use)

## Attribute Properties

| Property | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `name` | string | *required* | 3-32 chars, `^[a-z0-9\_]+$` | Attribute name (snake_case) |
| `kind` | string | *required* | Valid AttributeKind | Attribute type (see table above) |
| `label` | string | null | Max 32 chars | Display label (auto-generated if omitted) |
| `description` | string | null | Max 128 chars | Help text |
| `default_value` | any | null | - | Default value |
| `unique` | boolean | `false` | - | Must be globally unique for this model |
| `optional` | boolean | **`false`** | - | **Attributes are mandatory by default** |
| `read_only` | boolean | `false` | - | Cannot be modified |
| `order_weight` | integer | null | - | Display order (lower = first) |
| `enum` | list | null | - | List of valid values |
| `choices` | list[DropdownChoice] | null | - | Dropdown choices (for `Dropdown` kind) |
| `allow_override` | enum | `"any"` | `"none"` or `"any"` | Profile override behavior |
| `state` | enum | `"present"` | `present` or `absent` | Use `absent` to remove |
| `deprecation` | string | null | Max 128 chars | Deprecation message |

### Attribute Parameters (kind-specific)

**Text/TextArea parameters:**
```yaml
- name: hostname
  kind: Text
  parameters:
    regex: "^[a-zA-Z0-9-]+$"
    min_length: 3
    max_length: 64
```

**Number parameters:**
```yaml
- name: vlan_id
  kind: Number
  parameters:
    min_value: 1
    max_value: 4094
    excluded_values: "1,4094"    # Comma-separated values or ranges: "100,150-200,300-400"
```

### Computed Attributes

```yaml
- name: computed_field
  kind: Text
  read_only: true
  computed_attribute:
    kind: Jinja2                 # Options: User, Jinja2, TransformPython
    jinja2_template: "{% if asset_tag__value %}[{{ asset_tag__value }}](https://example.com){% else %}N/A{% endif %}"
```

### Dropdown Choices

```yaml
- name: status
  kind: Dropdown
  default_value: active
  choices:
    - name: active               # Internal value (required)
      label: Active              # Display text (optional)
      description: "Operational" # Help text (optional)
      color: "#00FF00"           # Hex color (optional)
    - name: planned
      label: Planned
      color: "#0000FF"
```

---

## Relationship Properties

| Property | Type | Default | Constraints | Description |
|----------|------|---------|-------------|-------------|
| `name` | string | *required* | 3-32 chars, `^[a-z0-9\_]+$` | Relationship name (snake_case) |
| `peer` | string | *required* | `^[A-Z][a-zA-Z0-9]+$` | Target kind (e.g., `DcimDeviceType`) |
| `kind` | enum | `"Generic"` | See table below | Relationship type |
| `label` | string | null | Max 32 chars | Display label |
| `description` | string | null | Max 128 chars | Help text |
| `identifier` | string | null | Max 128 chars, `^[a-z0-9\_]+$` | Must match on both sides of bidirectional relationships |
| `cardinality` | enum | **`"many"`** | `"one"` or `"many"` | How many related objects |
| `optional` | boolean | **`true`** | - | **Relationships are optional by default** |
| `direction` | enum | `"bidirectional"` | `bidirectional`, `outbound`, `inbound` | Relationship direction |
| `on_delete` | enum | null | `"no-action"` or `"cascade"` | Delete behavior |
| `order_weight` | integer | null | - | Display order |
| `min_count` | integer | 0 | - | Minimum related objects |
| `max_count` | integer | 0 | - | Maximum related objects (0 = unlimited) |
| `read_only` | boolean | `false` | - | Cannot be modified |
| `allow_override` | enum | `"any"` | `"none"` or `"any"` | Profile override behavior |
| `state` | enum | `"present"` | `present` or `absent` | Use `absent` to remove |
| `common_parent` | string | null | - | Peer must share same parent |
| `common_relatives` | list[string] | null | - | Peers must share same relatives |
| `deprecation` | string | null | Max 128 chars | Deprecation message |

### Relationship Kinds

| Kind | Use Case | Typical Pattern |
|------|----------|-----------------|
| `Generic` | Standard relationship between independent objects | Default. No special semantics. |
| `Attribute` | "Belongs to" style, displayed inline | `Device -> DeviceType`, `Device -> Rack` |
| `Component` | Parent owns children | `Device -> Interfaces` (parent side, `cardinality: many`) |
| `Parent` | Child points to parent | `Interface -> Device` (child side, `cardinality: one`) |
| `Group` | Group membership | Special group relationships |
| `Hierarchy` | Internal for hierarchical locations | Auto-managed by `hierarchical: true` |

### Component/Parent Pattern

Always define both sides with matching `identifier`:

```yaml
# On the parent (Device):
- name: interfaces
  peer: DcimInterface
  kind: Component
  cardinality: many
  identifier: "device__interface"

# On the child (Interface):
- name: device
  peer: DcimGenericDevice
  kind: Parent
  cardinality: one
  identifier: "device__interface"
```

---

## Extensions

Add attributes/relationships to nodes defined in other schema files:

```yaml
extensions:
  nodes:
    - kind: OrganizationProvider     # Existing node kind to extend
      attributes:                    # New attributes to add
        - name: website
          kind: URL
          optional: true
      relationships:                 # New relationships to add
        - name: sites
          peer: LocationSite
          cardinality: many
          optional: true
```

### NodeExtensionSchema Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `kind` | string | **Yes** | Kind of existing node to extend |
| `attributes` | list | No | New attributes to add |
| `relationships` | list | No | New relationships to add |
| `inherit_from` | list[string] | No | Additional generics to inherit |

---

## Menu Configuration

Menus are defined in separate YAML files:

```yaml
---
apiVersion: infrahub.app/v1
kind: Menu
spec:
  data:
    - namespace: Dcim
      name: DeviceManagement
      label: Device Management
      icon: "mdi:server"
      children:
        data:
          - namespace: Dcim
            name: Devices
            label: Devices
            kind: DcimGenericDevice    # Links to a node kind
            icon: "mdi:server"
```

### Menu Item Properties

| Property | Type | Description |
|----------|------|-------------|
| `namespace` | string | Namespace for the menu item |
| `name` | string | Unique name |
| `label` | string | Display text |
| `icon` | string | MDI/Iconify icon |
| `kind` | string | Optional - node kind for leaf items |
| `children.data` | list | Nested sub-menu items |

---

## Built-in Types

These types are built into Infrahub and can be referenced without defining them:

| Type | Description |
|------|-------------|
| `BuiltinTag` | Tag system (use in `tags` relationships) |
| `BuiltinIPAddress` | Base IP address (inherit from for IPAM) |
| `BuiltinIPPrefix` | Base IP prefix (inherit from for IPAM) |
| `CoreArtifactTarget` | Artifact generation target |

---

## order_weight Convention

| Range | Purpose |
|-------|---------|
| 900-999 | Primary relationships (manufacturer, rack, device_type) |
| 1000-1099 | Primary identifying attributes (name, model) |
| 1100-1499 | Secondary attributes (serial, part_number, description) |
| 1500-1999 | Tertiary attributes (optional fields, settings) |
| 2000-2999 | Advanced/computed/metadata fields |
| 3000+ | Tags and generic relationships (always last) |

---

## Naming Constraints Summary

| Element | Convention | Pattern | Length |
|---------|-----------|---------|--------|
| Node name | PascalCase | `^[A-Z][a-zA-Z0-9]+$` | 2-32 |
| Namespace | First upper, rest lower | `^[A-Z][a-z0-9]+$` | 3-32 |
| Attribute name | snake_case | `^[a-z0-9\_]+$` | 3-32 |
| Relationship name | snake_case | `^[a-z0-9\_]+$` | 3-32 |
| Identifier | snake_case | `^[a-z0-9\_]+$` | max 128 |
| Kind (auto) | Namespace + Name | - | - |
| Description | Free text | - | max 128 |
| Label (attr/rel) | Free text | - | max 32 |
| Label (node) | Free text | - | max 64 |
