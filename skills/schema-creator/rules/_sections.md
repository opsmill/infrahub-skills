# Infrahub Schema Creator - Rule Sections

1. **Naming Conventions (naming-)** — CRITICAL.
   Namespace, node, generic, and attribute naming
   patterns. Kind derivation rules. Violations cause
   schema validation failures.

2. **Relationships (relationship-)** — CRITICAL.
   Bidirectional identifier matching, peer references,
   Component/Parent pairing, cardinality and optional
   defaults. Incorrect relationships cause silent
   data model bugs.

3. **Attributes (attribute-)** — HIGH.
   Mandatory-by-default behavior, Dropdown choices
   format, deprecated field names. Misunderstanding
   defaults leads to unexpected required fields.

4. **Hierarchy (hierarchy-)** — HIGH. Setting up
   hierarchical generics and nodes with parent/children
   fields. Required for location trees and any
   parent-child taxonomy.

5. **Display (display-)** — HIGH. human_friendly_id,
   display_label, and order_weight configuration.
   Controls how objects are identified and displayed
   in the UI and object references.

6. **Extensions (extension-)** — MEDIUM. Adding
   attributes/relationships to nodes defined in other
   schema files. Enables modular schema design across
   multiple files.

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
