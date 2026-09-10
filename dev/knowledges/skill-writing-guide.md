# Skill Writing Guide

Best practices for writing effective Infrahub skills,
distilled from the skill-creator methodology.

## Description Field

The `description` in SKILL.md frontmatter is the most
important line in the entire skill — it determines
whether the AI activates the skill at all.

### What makes a good description

- Include the primary action AND specific trigger
  contexts
- Mention synonyms and adjacent concepts users might
  say
- Use TRIGGER/DO NOT TRIGGER patterns to disambiguate
- Lean slightly "pushy" — AI tools tend to
  *under-trigger* skills

**Good:**

```yaml
description: >-
  Create, validate, and modify Infrahub schemas.
  Use when designing data models, creating schema
  nodes with attributes and relationships,
  validating schema definitions, or planning
  schema migrations for Infrahub.
```

**Bad:**

```yaml
description: Schema creation tool
```

### Description optimization

Use `/skill-creator` to run the description
optimization loop — it generates trigger eval queries,
tests them, and iteratively improves the description
for better triggering accuracy.

## SKILL.md Body

### Structure

1. **Overview** — 1-2 paragraphs, what and when
2. **Workflow** — Numbered steps the AI follows
3. **Rule Categories** — Links to rule sections
4. **Supporting References** — When to read each
   supporting file

### Size budget

Keep SKILL.md under 500 lines. If approaching this
limit, add hierarchy: move details to supporting files
and keep SKILL.md as the navigator.

### Writing style

**Explain the why, not just the what.** AI models are
smart — they respond to reasoning better than rigid
commands. Instead of "ALWAYS use full kind references",
write "Use full kind references (e.g., `IpamVlanGroup`
not `VlanGroup`) because Infrahub resolves
relationships by full namespace+name, and short names
cause lookup failures."

**Use imperative form.** "Check the namespace" not
"You should check the namespace."

**Include inline examples for critical patterns.**
Models learn from concrete examples more reliably than
from abstract rules:

```markdown
## Relationship Identifiers

Both sides of a relationship must share the same
identifier so Infrahub knows they're the same link:

**Correct:**
Node A: identifier: "device__interfaces"
Node B: identifier: "device__interfaces"

**Wrong:**
Node A: identifier: "device__interfaces"
Node B: identifier: "interfaces__device"
```

## Rules

### One rule, one concern

Each rule file should cover exactly one thing. A rule
about naming conventions should not also cover display
labels. This keeps rules independently addressable —
the AI loads only what's relevant.

### Rule structure

Every rule file should answer:

1. **What is the rule?** — One-sentence summary
2. **Why does it matter?** — The reasoning (failures,
   confusing behavior, data loss)
3. **How to apply it** — The specific check or pattern
4. **Examples** — Compliant and non-compliant, in
   two separate fenced blocks. One fence holding
   both makes a single document the AI reads as one
   artifact, so the WRONG half gets copied along
   with the RIGHT half.
5. **Common mistakes** — What typically goes wrong
   (this is gold for AI models)

### Category prefixes

Rules are named with a category prefix from
`_sections.md` (`naming-conventions.md`,
`relationship-identifiers.md`,
`display-order-weight.md`), so rules are findable by
domain and new ones need no renaming. Registering a
new prefix touches more than `_sections.md` — see
[adding-a-rule.md](../guides/adding-a-rule.md#1-write-the-rule).

### One fact, one home

State a list, a claim, or a command in exactly one
file and point at it from everywhere else. The
failure is not the duplication itself, it is that the
copies drift: a read-only command allowlist written
into four files ends up with three different
memberships, and nobody can tell which is current.

This binds graders too. A grader that hard-codes a
command tree, a kind list, or a set of valid flags
holds a second copy of the skill's prose, and the two
diverge the first time the prose changes. Derive it
from one place, or assert the shape rather than the
membership.

### Say only what you verified

Write the claim you actually tested, at the strength
you tested it. "Verified against Infrahub 1.11.0"
means the check ran on 1.11.0 — if it ran on
something else, or on nothing, drop the line. An
unverified provenance claim is worse than no claim,
because the next author trusts it instead of
re-checking.

## Examples File

The `examples.md` file is high-value — models learn
from concrete patterns more reliably than from
abstract instructions.

### What to include

- 2-3 complete, realistic examples at different
  complexity levels
- Each example should be a full, working artifact
  (not a fragment)
- Cover the most common use cases first, then edge
  cases
- Include comments explaining non-obvious choices

### What to avoid

- Trivial examples that don't exercise the rules
  (too simple to learn from)
- Overly complex examples that obscure the core
  pattern
- Examples that work around bugs or legacy behavior
  (document the current best practice)

### Every snippet must stand on its own

An example is copied, not read. Each one has to name
only kinds, attributes, fields, and packages that
exist in what it shows — a snippet referring to an
attribute the schema above it never defines cannot be
run, and the quoted error it promises will never
appear. Before shipping a snippet, load or execute it
against the artifact it sits next to.

### Read the example back against the rule

The commonest defect in a corrected rule is an
example that demonstrates something other than the
sentence introducing it — often the inverse, because
the rule's lead was rewritten and the example wasn't.
After editing either half, read the lead sentence and
the example together and check the example would fail
for the reason the lead gives.

## Common Pitfalls

### Overfitting to specific examples

When iterating on a skill with a small eval set, it's
tempting to add narrow fixes that only help those
specific cases. Instead, generalize: if the AI gets
VLAN naming wrong, the fix should improve naming
guidance broadly, not add a VLAN-specific exception.

### Too many MUSTs

Piling on rigid constraints ("MUST use X", "NEVER do
Y", "ALWAYS check Z") makes the skill brittle and
hard to maintain. Use explanation and reasoning
instead — the AI will generalize better.
