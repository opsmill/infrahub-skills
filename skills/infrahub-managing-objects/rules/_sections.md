# Infrahub Object Creator - Rule Sections

1. **File Format (format-)** -- CRITICAL. apiVersion,
   kind: Object, spec structure, required and optional
   fields. Every object file must follow this exact
   structure.

2. **Value Mapping (value-)** -- CRITICAL. How schema
   attribute types map to YAML values. Dropdown name vs
   label, relationship references by human_friendly_id
   (scalar vs list), group membership. Generic
   relationship references using inline data blocks with
   explicit `kind:` when the target is a generic type
   without `human_friendly_id`.

3. **Children (children-)** -- HIGH. Nesting hierarchical
   children (location trees) and component children
   (interfaces, modules). Always requires `kind`
   specification on the nested block.

4. **Range Expansion (range-)** -- MEDIUM. Using
   `expand_range: true` to generate sequential interfaces
   (e.g., Ethernet1/[1-4]). Must be set on the
   relationship block via `parameters`.

5. **File Organization (organization-)** -- MEDIUM. Numeric
   prefix naming convention, dependency load order,
   multi-document files, one kind per document rule.

6. **Common Patterns (patterns-)** -- LOW. Ready-to-use
   patterns: flat lists, parent-child inline, devices with
   references, empty slots, git repos.
