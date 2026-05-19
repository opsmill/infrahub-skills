# Infrahub Schema Creator - Rule Sections

1. **Naming Conventions (naming-)** — CRITICAL.
   Namespace, node, generic, and attribute naming
   patterns. Kind derivation rules. Violations cause
   schema validation failures.

2. **Relationships (relationship-)** — CRITICAL.
   Bidirectional identifier matching, peer references,
   Component/Parent pairing, cardinality and optional
   defaults, `on_delete` cascade vs no-action.
   Incorrect relationships cause silent data model
   bugs and orphaned objects on delete.

3. **Attributes (attribute-)** — HIGH.
   Mandatory-by-default behavior, Dropdown choices
   format, computed Jinja2 attributes (`read_only`
   plus `optional: false` combo), branch-agnostic
   identity fields, deprecated field names.

4. **Hierarchy (hierarchy-)** — HIGH. Setting up
   hierarchical generics and nodes with parent/children
   fields. Required for location trees and any
   parent-child taxonomy.

5. **Display (display-)** — HIGH. human_friendly_id,
   display_label, order_weight, and menu placement
   (`include_in_menu: false`, `menu_placement:`).
   Controls how objects are identified, ordered, and
   surfaced in the UI sidebar.

6. **Extensions (extension-)** — MEDIUM. Adding
   attributes/relationships to nodes defined in other
   schema files. Capability flags applied at the node
   level: artifact targets
   (`inherit_from: CoreArtifactTarget`) and Object
   Templates (`generate_template: true`) — independent
   features, kept in separate rule files.

7. **Uniqueness (uniqueness-)** — MEDIUM. Uniqueness
   constraint format with __value suffix for
   attributes. Incorrect format causes validation
   errors.

8. **Migration (migration-)** — MEDIUM. Adding,
   removing, and renaming attributes safely. Using
   state: absent. Strategies for non-breaking schema
   changes.

9. **Validation (validation-)** — LOW. Common
   validation errors and their fixes. Pre-validation
   checklist before running infrahubctl schema check.
