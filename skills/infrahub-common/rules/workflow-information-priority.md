---
title: Information-Source Priority
impact: MEDIUM
tags: workflow, references, external-docs, web-search, source-priority, llms-txt, documentation-fallback
---

## Information-Source Priority

Impact: MEDIUM

When answering an Infrahub question that the loaded skills already cover
(schemas, objects, checks, generators, transforms, menus, data analysis,
repository audits), read the active skill's own rules and reference files
before reaching for external documentation or a web search. When the
question is genuinely outside what any loaded skill covers, fall back to
the official documentation using the procedure below — do not guess from
training.

### Why it matters

The skill's `rules/`, `reference.md`, `examples.md`, and the shared
`infrahub-common/` references are curated for the Infrahub version this
plugin targets and encode gotchas that generic sources miss — `Text` over
the deprecated `String`, singular `display_label`, matched relationship
identifiers on both peers, full kind references. External docs and model
training are often a version behind, or silent on these, so skipping
straight to them produces answers that contradict the skill's tested
guidance and reintroduce the exact mistakes the rules exist to prevent.
It also burns turns fetching what is already in context. But when the
skills are genuinely silent on a real Infrahub question, a guessed answer
is worse than one grounded in the official docs — so the fallback below
exists for exactly that case.

### Priority order

1. **The active skill's own files** — its `rules/`, `reference.md`,
   `examples.md`, and `validation.md`.
2. **Shared `infrahub-common/` references** — `graphql-queries.md`,
   `infrahub-yml-reference.md`, `netbox-vs-infrahub.md`, and the
   cross-cutting `rules/`.
3. **Last resort: the official Infrahub documentation**, consulted with
   the procedure below — only when the answer is genuinely absent from
   steps 1–2, and say so explicitly so the gap can be filled in a skill
   later.

### Consulting the documentation on a gap

Applies only when steps 1–2 do not cover the task and it is still an
Infrahub question (e.g. deleting a node, git-integration semantics).

1. **Find the page.** Search the index at
   `https://docs.infrahub.app/llms.txt`. With a shell, grep it, which
   reads every line:

   ```bash
   curl -s https://docs.infrahub.app/llms.txt | grep -i '<topic>'
   ```

   Without a shell, use your web-fetch tool (WebFetch in Claude Code;
   the equivalent in Cursor/Copilot/Windsurf) with a *targeted*
   question: "Which page paths under the `## <section>` heading cover
   <topic>?" The index is about 200 KB, and the core product sections
   (`## branches`, `## generators`, `## menu`, `## schema`,
   `## transformations`, ...) come after the satellite products
   (ansible, backup, mcp, python-sdk, sync, ...). A web-fetch tool that
   summarises a truncated copy can miss them and return a satellite
   page instead, so name the section and check the path you get back
   belongs to it.
2. **Read the page.** Each index entry is already a Markdown path such
   as `/branches/delete.md`. Fetch `https://docs.infrahub.app<path>`
   and answer from it. Take the path from the index: adding `.md` to a
   docs URL cited elsewhere fails for older `/topics/...` URLs, which
   redirect and have no Markdown version.
3. **Cite and caveat.** Cite the page URL and add a short note that the
   point is outside the skill's tested rules and should be verified, so
   the gap can later be folded into a skill.

Do not fetch `llms-full.txt`. It is a bulk export of about 6 MB that
will not fit in context. The index-then-page path above is the
supported route.

If `llms.txt` or the page cannot be fetched (a network error, or an HTML
404 shell whose body starts with `<!doctype` or contains `<html>`), say
so explicitly and give a best-effort answer clearly flagged as
unverified. Never present training recall as authoritative when the docs
were unreachable.

### Examples

Compliant — a question about which attribute type to use is answered from
the schema skill's `reference.md` and the `attribute-defaults-and-types`
rule, which specify `Text` rather than the deprecated `String`.

Compliant — a question about deleting a node (not covered by any loaded
skill) is answered by fetching `llms.txt` to locate the data-management
page, fetching that page's `.md`, and answering with the page cited plus
a "outside the skill's tested rules — verify" caveat.

Non-compliant — the same attribute-type question is answered from a web
search that suggests `String`, contradicting the rule and shipping a
deprecated type.

Non-compliant — a delete-node question is answered straight from training
with no doc lookup and no caveat, or by dumping `llms-full.txt` into
context.

### Common mistakes

- Treating a fetched doc page or training recall as authoritative over a
  skill rule that addresses the same point. The rule wins — it is
  version-matched to this plugin.
- Fetching `llms-full.txt` (or the entire `llms.txt`) into context
  instead of the targeted index-then-page lookup.
- Answering a genuine gap silently from training — without consulting the
  docs, or without flagging that the answer is outside the skill's tested
  rules.
- Searching the web for `.infrahub.yml` fields or GraphQL syntax that
  `infrahub-common/` already lays out.
- Reaching for external docs without first checking whether the active
  skill's reference files answer the question.

Reference: [Infrahub Docs](https://docs.infrahub.app) ·
[llms.txt index](https://docs.infrahub.app/llms.txt)
