---
title: Information-Source Priority
impact: MEDIUM
tags: workflow, references, external-docs, web-search, source-priority
---

## Information-Source Priority

Impact: MEDIUM

When answering an Infrahub question that the loaded skills
already cover (schemas, objects, checks, generators,
transforms, menus, data analysis, repository audits), read
the active skill's own rules and reference files before
reaching for external documentation or a web search.

### Why it matters

The skill's `rules/`, `reference.md`, `examples.md`, and the
shared `infrahub-common/` references are curated for the
Infrahub version this plugin targets and encode gotchas that
generic sources miss — `Text` over the deprecated `String`,
singular `display_label`, matched relationship identifiers
on both peers, full kind references. External docs and model
training are often a version behind, or silent on these, so
skipping straight to them produces answers that contradict
the skill's tested guidance and reintroduce the exact
mistakes the rules exist to prevent. It also burns turns
fetching what is already in context.

### Priority order

1. **The active skill's own files** — its `rules/`,
   `reference.md`, `examples.md`, and `validation.md`.
2. **Shared `infrahub-common/` references** —
   `graphql-queries.md`, `infrahub-yml-reference.md`,
   `netbox-vs-infrahub.md`, and the cross-cutting `rules/`.
3. **Last resort: external Infrahub documentation**
   (`docs.infrahub.app`) or a web search — only when the
   answer is genuinely absent above, and say so explicitly
   so the gap in the skill can be filled later.

### Examples

Compliant — a question about which attribute type to use is
answered from the schema skill's `reference.md` and the
`attribute-defaults-and-types` rule, which specify `Text`
rather than the deprecated `String`.

Non-compliant — the same question is answered from a web
search that suggests `String`, contradicting the rule and
shipping a deprecated type.

### Common mistakes

- Treating a fetched doc page or training recall as
  authoritative over a skill rule that addresses the same
  point. The rule wins — it is version-matched to this plugin.
- Searching the web for `.infrahub.yml` fields or GraphQL
  syntax that `infrahub-common/` already lays out.
- Reaching for external docs without first checking whether
  the active skill's reference files answer the question.

Reference: [Infrahub Docs](https://docs.infrahub.app)
