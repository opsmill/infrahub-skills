# Infrahub Object Creator - Rule Sections

1. **Branch-First Loading (workflow-)** -- CRITICAL. Load
   objects onto a dedicated branch (`--branch`), not the
   default branch (`main` by convention), on any shared
   server. A bad load on the default branch is a per-object
   cleanup; on a branch it is a single discard — and the
   branch routes the change through proposed-change review.

2. **File Format (format-)** -- CRITICAL. apiVersion,
   kind: Object, spec structure, required and optional
   fields. Every object file must follow this exact
   structure.

3. **Value Mapping (value-)** -- CRITICAL. How schema
   attribute types map to YAML values. Dropdown name vs
   label, relationship references by human_friendly_id
   (scalar vs list), group membership. Generic
   relationship references using inline data blocks with
   explicit `kind:` when the target is a generic type
   without `human_friendly_id`. Profile assignment
   (`profiles:` list) and Object Template instantiation
   (`object_template`) are relationship references too — see
   value-profiles-templates.

4. **Children (children-)** -- HIGH. Nesting hierarchical
   children (location trees) and component children
   (interfaces, modules). Always requires `kind`
   specification on the nested block.

5. **Range Expansion (range-)** -- MEDIUM. Using
   `expand_range: true` to generate sequential interfaces
   (e.g., Ethernet1/[1-4]). Must be set on the
   relationship block via `parameters`.

6. **File Organization (organization-)** -- MEDIUM. Numeric
   prefix naming convention, dependency load order,
   multi-document files, one kind per document rule.

7. **Common Patterns (patterns-)** -- LOW. Ready-to-use
   patterns: flat lists, parent-child inline, devices with
   references, empty slots, git repos.
