---
title: audit-cites-all-reference-sites
impact: HIGH
tags: audit, conduct, evidence, findings
---

# Rule: audit-cites-all-reference-sites

**Severity**: HIGH
**Category**: Conduct

## What It Checks

Every finding that proposes removing or renaming a
symbol enumerates all of its reference sites in a
`sites` list, obtained from a repo-wide search. The
finding's own `file:line` locates the finding; it is
not the answer. Where a finding names a render or
execution site, that site is established from the
registration graph rather than from the filename.

## Why it matters

An implementer treats the cited location as the set of
places to change. When the set is short, they change
what the finding named, the audit closes, and the
repository is left referencing a symbol that no longer
exists. The break surfaces later as a render or query
failure with no obvious connection to the change, in a
component nobody edited.

Both halves of this have been observed in a single
audit. One finding named two sites where a repo-wide
grep found eight: the schema, two templates, three
queries and two places in a generator. Two others named
an unregistered per-section template as the render site
when the live path ran through a different template
reached from the registered composed one. The orphan
had the more canonical-looking name, which is exactly
why a filename is not evidence.

## Checks

1. **Removal and rename findings carry `sites`**: a
   list of every reference, from a repo-wide search
   across schemas, object files, queries, templates,
   transforms, generators and checks. Not the first
   site found.
2. **`sites` is complete or declared incomplete**: if
   the sweep was not run, the finding says so rather
   than presenting a partial list as the set.
3. **Render and execution sites come from the
   registration graph**: read `.infrahub.yml` for what
   is registered, then walk the include and import
   closure for what is reachable from it. A file that
   nothing includes is not a render site. If such a file
   mentions the symbol anyway, report it separately as
   dead code; it does not belong in `sites`, which is
   the set of live references the fix has to touch.
4. **The include scan accepts both quote styles** for
   `include`, `import`, `extends` and `from`. A scan
   matching only `{% include 'x.j2' %}` misses
   `{%- import "x.j2" -%}` and reports a reachable
   template as unreferenced. The failure is silent.
5. **A snippet offered as a search-and-replace target
   lists every block it matches.** The `sites` entries
   are the match count. If the snippet matches three
   blocks and the finding intends two, the third is
   either a site or a reason to narrow the snippet.

## Example

A finding proposing to drop a denormalized
`site_name` attribute:

```json
{
  "rule": "yagni-denormalized-vs-indirect-relationship",
  "severity": "MEDIUM",
  "ladder_step": 2,
  "file": "schemas/dcim.yml",
  "line": "42",
  "sites": [
    "schemas/dcim.yml:42",
    "templates/device_config.j2:15",
    "templates/device_interfaces.j2:8",
    "queries/device_info.gql:12"
  ]
}
```

`templates/device_interfaces.j2` appears because the
registered template imports it with double quotes.
`templates/device.j2`, which nothing includes, does
not appear at all.

## Common Issues

- `file:line` given with no `sites` list, implying the
  single location is the whole set
- A partial list presented in the same voice as a
  complete one, with no note that no sweep was run
- An unregistered file cited as the render site
  because its name looks canonical
- An include scan matching one quote style, reporting
  a reachable template as an orphan
- A replacement snippet whose real match count in the
  file is higher than the finding describes
