# Infrahub CSV Import — Rule Sections

1. **Workflow (workflow-)** — CRITICAL. Introspect
   the schema first, fail closed on unmapped
   columns, batch all ambiguities into one up-front
   interview, self-check against managing-objects
   before any server call, and create the import
   branch as a deliberate step before validate or
   load.

2. **Inputs (inputs-)** — HIGH. Accept any
   combination of a single file, a directory
   (recursive `*.csv` / `*.tsv` scan), or a list of
   paths. Normalize to a flat file list before
   profiling so downstream logic doesn't branch on
   input shape.

3. **Mapping (mapping-)** — CRITICAL. Translate
   columns into attributes, relationships, and
   component children using the heuristic order in
   [../reference.md](../reference.md). Translate
   dropdown labels to choice names. Detect
   reference columns by name+shape and emit the
   scalar/list form that matches the target's
   `human_friendly_id`.

4. **Decomposition (decomposition-)** — HIGH. A
   denormalized CSV (one big sheet conflating
   multiple kinds, or repeated parent rows per
   child) gets split into the right kinds with
   correct load order. The user confirms the split
   in the interview.

5. **Range (range-)** — MEDIUM. Detect
   interface-shaped sequences (`eth0..eth47` for
   one parent, identical sibling-column values) and
   collapse to bracket-range syntax with
   `parameters.expand_range: true` on the
   relationship block.

6. **Lineage (lineage-)** — LOW. Optional
   stamping of every imported value with a
   `source` reference. Lineage only — `source` does
   not lock the value; locking needs `owner` +
   `is_protected`.

7. **Outputs (outputs-)** — LOW. Cross-cutting
   shape concerns for the emitted files themselves
   (file-level provenance comments, etc.) that
   apply to every kind regardless of mapping
   decisions.
