# Infrahub Menu Creator - Rule Sections

1. **File Format (format-)** -- CRITICAL. apiVersion,
   kind: Menu, spec structure. Required top-level
   fields for every menu file.

2. **Item Properties (item-)** -- CRITICAL. All menu
   item properties: name, namespace, label, kind,
   path, icon, order_weight, parent, children.
   Use kind OR path, not both.

3. **Hierarchy (hierarchy-)** -- HIGH. Nesting children
   with children.data wrapping, group headers
   (no kind = non-clickable), unlimited nesting depth.

4. **Icons (icons-)** -- HIGH. Material Design Icons
   (MDI) library reference with mdi: prefix. Common
   icon choices for infrastructure types.

5. **Schema Integration (schema-)** -- MEDIUM. Setting
   include_in_menu: false on schema nodes when using
   custom menus, kind auto-resolves to correct URL.

6. **Patterns (patterns-)** -- LOW. Ready-to-use
   patterns: flat menu, nested hierarchy,
   commented-out items, direct links to generic
   node lists.
