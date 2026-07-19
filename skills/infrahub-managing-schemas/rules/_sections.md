# Infrahub Schema Creator - Rule Sections

1. **Workflow (workflow-)** — CRITICAL. Apply
   schema changes on a dedicated branch (`--branch`), not
   the default branch (`main` by convention), on any shared
   server. Schema loads run migrations against loaded data
   immediately and globally; a branch makes the change
   previewable, isolated, and discardable, and routes it
   through proposed-change review. Also covers offline file
   hygiene — running `infrahubctl schema format` to
   normalise key ordering before check/load.

2. **Naming Conventions (naming-)** — CRITICAL.
   Namespace, node, generic, and attribute naming
   patterns. Kind derivation rules. Violations cause
   schema validation failures.

3. **Relationships (relationship-)** — CRITICAL.
   Bidirectional identifier matching, peer references,
   Component/Parent pairing, cardinality and optional
   defaults, `on_delete` cascade vs no-action.
   Incorrect relationships cause silent data model
   bugs and orphaned objects on delete.

4. **Attributes (attribute-)** — HIGH.
   Mandatory-by-default behavior, Dropdown choices
   format, computed Jinja2 attributes (`read_only`
   plus `optional: false` combo), branch-agnostic
   identity fields, deprecated field names.

5. **Hierarchy (hierarchy-)** — HIGH. Setting up
   hierarchical generics and nodes with parent/children
   fields. Required for location trees and any
   parent-child taxonomy.

6. **Display (display-)** — HIGH. human_friendly_id,
   display_label, order_weight, and menu placement
   (`include_in_menu: false`, `menu_placement:`).
   Controls how objects are identified, ordered, and
   surfaced in the UI sidebar.

7. **Extensions (extension-)** — MEDIUM. Adding
   attributes/relationships to nodes defined in other
   schema files. Capability flags applied at the node
   level: artifact targets
   (`inherit_from: CoreArtifactTarget`) and Object
   Templates (`generate_template: true`) — independent
   features, kept in separate rule files. Profiles
   (`generate_profile: true`) enable shared default values via
   a companion Profile<Kind> node.

8. **Uniqueness (uniqueness-)** — MEDIUM. Uniqueness
   constraint format with __value suffix for
   attributes. Incorrect format causes validation
   errors.

9. **Migration (migration-)** — MEDIUM. Adding,
   removing, and renaming attributes safely. Using
   state: absent. Strategies for non-breaking schema
   changes.

10. **Validation (validation-)** — HIGH for
    string-length caps (load-time `string_too_long`
    on `description` / `label` / `identifier` /
    `deprecation`), otherwise LOW. Pre-validation
    checklist and common error messages with
    cross-links to the detail rules.
