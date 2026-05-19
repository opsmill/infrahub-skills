# Infrahub Repository Audit Procedure

This document defines the step-by-step audit procedure.
When running an audit, follow each phase in order and
collect findings into a structured report.

## Phase 1: Project Structure (CRITICAL)

### 1.1 Check `.infrahub.yml` exists

- Look for `.infrahub.yml` in project root
- If missing: CRITICAL finding — "No .infrahub.yml
  found. This file is required to connect the
  repository to Infrahub."

### 1.2 Parse `.infrahub.yml` sections

- Validate YAML syntax
- Check for recognized top-level keys: `schemas`,
  `menus`, `objects`, `queries`, `check_definitions`,
  `python_transforms`, `jinja2_transforms`,
  `artifact_definitions`, `generator_definitions`
- Flag any unrecognized top-level keys

### 1.3 Validate file paths

- For every `file_path`, `template_path`, and directory
  reference in `.infrahub.yml`, verify the file/directory
  exists on disk
- CRITICAL if referenced files are missing

### 1.4 Validate required fields per section

- `queries`: each entry needs `name` and `file_path`
- `check_definitions`: each entry needs `name` and
  `file_path`
- `python_transforms`: each entry needs `name` and
  `file_path`
- `jinja2_transforms`: each entry needs `name`, `query`,
  and `template_path`
- `artifact_definitions`: each entry needs `name`,
  `parameters`, `content_type`, `targets`,
  `transformation`
- `generator_definitions`: each entry needs `name`,
  `file_path`, `query`, `targets`

---

## Phase 2: Schema Audit (CRITICAL)

Find all schema files (directories/files listed under
`schemas:` in `.infrahub.yml`, or `schemas/` by
convention).

### 2.1 Schema file format

- Must be valid YAML
- Must contain `version: "1.0"` (or current version)
- Should contain `nodes:` and/or `generics:` top-level
  keys

### 2.2 Naming conventions

- **Namespace**: `^[A-Z][a-z0-9]+$` (3-32 chars) —
  check every node and generic
- **Node/Generic name**: `^[A-Z][a-zA-Z0-9]+$`
  (2-32 chars)
- **Attribute names**: `^[a-z0-9_]+$` (3-32 chars)
- **Relationship names**: `^[a-z0-9_]+$` (3-32 chars)
- **Kind**: must be `Namespace` + `Name` concatenation

### 2.3 Attribute checks

- Attributes default to `optional: false` — flag new
  attributes without `optional: true` or `default_value`
  (INFO level, since this may be intentional)
- Dropdown `choices` must be objects with `name` field
  (not bare strings)
- Check for deprecated field names: `String` kind
  (should be `Text`), `default_filter` (should be
  `human_friendly_id`)
- For `display_labels` deprecation, see dedicated
  section 2.9 below

### 2.4 Relationship checks

- `peer` field must use full kind (Namespace + Name),
  not just name
- Bidirectional relationships: both sides must share
  the same `identifier`
- Identifier convention: `__` separator
  (e.g., `parent__children`)
- Component relationships:
  `kind: Component` + `cardinality: many`
- Parent relationships:
  `kind: Parent` + `cardinality: one`
- Component/Parent pairs must share the same `identifier`

### 2.5 Hierarchy checks

- If any node/generic has `hierarchical: true`, verify:
  - A generic exists with `hierarchical: true`
  - Nodes specify `parent` and `children` fields
  - Root nodes have `parent: null`
  - Leaf nodes have `children: null`
  - Full kind used in `parent` and `children` values

### 2.6 Display settings

- All user-facing nodes should have `human_friendly_id`
  defined (MEDIUM)
- `human_friendly_id` path syntax:
  `attribute__value` or `relationship__attribute__value`
- Recommend `display_label` for UI rendering

### 2.7 Uniqueness constraints

- Attribute fields in constraints must use `__value`
  suffix
- Relationship fields use bare name (no suffix)
- All referenced fields must exist on the node

### 2.8 Extensions

- Cross-file relationships should use `extensions` block
- Check `extensions` block structure is correct

### 2.9 Deprecated `display_labels` migration (HIGH)

- Scan all schema files for any node or generic
  containing the `display_labels` key (plural, list
  format)
- Severity: **HIGH** — deprecated since Infrahub v1.5,
  will be removed in a future release
- For each occurrence, output:
  - The file path and node/generic name
  - The current `display_labels` value (the list)
  - The exact `display_label` replacement (Jinja2
    template string)
- Conversion: wrap each list item in `{{ }}`, join
  with spaces into a single string
  - Example: `display_labels: ["name__value"]` →
    `display_label: "{{ name__value }}"`
  - Example: `display_labels: ["form_factor__value",
    "sfp_type__value"]` →
    `display_label: "{{ form_factor__value }} {{ sfp_type__value }}"`
- See
  [rules/schema-display-labels-deprecated.md](rules/schema-display-labels-deprecated.md)
  for full migration patterns
- Validation:
  `infrahubctl schema check <path/to/schema/files>`

---

## Phase 3: Object Data Audit (CRITICAL)

Find all object files (directories listed under
`objects:` in `.infrahub.yml`, or `objects/` by
convention).

### 3.1 YAML document structure

- Each YAML document must have:
  `apiVersion: infrahub.app/v1`, `kind: Object`,
  `spec.kind`, `spec.data`
- `spec.data` must be a list
- One kind per document (multiple documents separated
  by `---` are OK)

### 3.2 Value types

- Text attributes → string values
- Number attributes → integer values
- Boolean attributes → true/false
- Dropdown attributes → choice `name` (not label)
- DateTime attributes → ISO format string

### 3.3 Relationship references

- Cross-reference with schema: single-element
  `human_friendly_id` → scalar reference,
  multi-element → list
- References must match target node's
  `human_friendly_id` structure

### 3.4 Children and components

- Hierarchical children must include `kind` field at
  each level
- Component children require `kind` field under
  relationship name
- Structure: relationship → `kind` + `data` array

### 3.5 Range expansion

- `expand_range: true` must be in `parameters` block,
  NOT on individual data items
- Range syntax: `[start-end]` with inclusive bounds

### 3.6 File organization

- Check numeric prefix naming (01_, 02_, 03_) for
  dependency ordering
- Bootstrap files must NOT be in `objects/` directory
- Load order: independent objects → types → templates
  → locations → instances → metadata

---

## Phase 4: Python Components Audit (CRITICAL)

### 4.1 Check classes

- Must inherit from `InfrahubCheck`
- Must implement `validate(self, data: dict)`
  (sync or async)
- Must have `query` class attribute
- Should use `self.log_error()` for failures
- Must NOT use `log_warning()` (does not exist)
- GraphQL query should include `id` and `__typename`
  fields

### 4.2 Generator classes

- Must inherit from `InfrahubGenerator`
- Must implement `async generate(self, data: dict)`
- Must use `await self.client.create()` for object
  creation
- Must call `save(allow_upsert=True)` on created objects
- Should handle empty/missing data gracefully

### 4.3 Transform classes

- Must inherit from `InfrahubTransform`
- Must implement `transform(self, data: dict)`
  (sync or async)
- Must have `query` class attribute
- Return type: `dict` for JSON, `str` for text/plain

### 4.4 Jinja2 templates

- Valid Jinja2 syntax
- Access data via `data` variable
- Template imports resolve correctly

---

## Phase 5: Cross-Reference Integrity (HIGH)

### 5.1 Query name matching

- For every check/generator/transform: the `query`
  class attribute in Python must match a `name` in
  `queries` section of `.infrahub.yml`
- For every `jinja2_transforms` entry: the `query`
  field must match a query `name`

### 5.2 Target group consistency

- All `targets` referenced in `.infrahub.yml` should
  be documented or exist as `CoreStandardGroup` /
  `CoreGeneratorGroup`
- Generator targets must be `CoreGeneratorGroup`

### 5.3 Artifact → Transform linkage

- Every `artifact_definitions.transformation` must
  match a transform `name` (python or jinja2)
- Content type should match the transform's return type

### 5.4 Parameter mapping

- Parameters must map valid query variables to valid
  attribute paths
- Attribute paths use `__` notation
  (e.g., `name__value`)

---

## Phase 6: Registration Completeness (HIGH)

### 6.1 Orphan detection

- Python files in `checks/`, `generators/`,
  `transforms/` directories that are NOT registered
  in `.infrahub.yml`
- `.gql` files not referenced by any query entry
- Jinja2 templates not referenced by any transform
- Schema files not under a `schemas:` path

### 6.2 Missing registrations

- Python files with `InfrahubCheck` /
  `InfrahubGenerator` / `InfrahubTransform` subclasses
  that aren't in `.infrahub.yml`

---

## Phase 7: Best Practices (MEDIUM)

### 7.1 Schema best practices

- `human_friendly_id` on all user-facing nodes
- `display_label` set for UI rendering
- `order_weight` in recommended ranges (800-900 key
  relationships, 1000-1999 core, 2000-2999 secondary,
  3000+ metadata)
- Generics used for shared attributes across multiple
  nodes

### 7.2 Object best practices

- Numeric prefix naming for load order
- No bootstrap files in `objects/` directory

### 7.3 Check/Generator/Transform best practices

- Error collection before logging in checks
- `allow_upsert=True` on generator saves
- `delete_unused_nodes=True` for generator cleanup
- Shared utility functions in common.py when patterns
  repeat

---

## Phase 8: Deployment Readiness (MEDIUM)

### 8.1 Git status

- All files referenced in `.infrahub.yml` should be
  committed
- No uncommitted changes to schema, query, Python,
  or template files
- `.infrahub.yml` itself must be committed

### 8.2 Bootstrap files

- Files intended for one-time loading must NOT be in
  `objects/` directory
- Bootstrap data should be in a separate directory
  (e.g., `bootstrap/`)

### 8.3 Display label caching

- Warn if `display_label` references parent
  relationships (may compute incorrectly during
  batch loading)
- Suggest loading parent objects before children

---

## Report Generation

After all phases, produce a markdown report with:

1. **Summary** — total findings by severity,
   pass/fail per category
2. **Per-category sections** — each finding with
   severity, description, file location, and
   suggested fix
3. **Cross-reference table** — mapping of
   queries ↔ Python files ↔ `.infrahub.yml` entries

### Severity Levels

| Level | Meaning |
| ----- | ------- |
| CRITICAL | Will cause failures — schema, sync, pipelines |
| HIGH | Likely issues — silent failures, broken refs |
| MEDIUM | Best practice violation — suboptimal but works |
| LOW | Style/organization suggestion |
| INFO | Informational observation, no action needed |
