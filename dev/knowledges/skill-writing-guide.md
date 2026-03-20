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
4. **Examples** — Compliant and non-compliant, side
   by side
5. **Common mistakes** — What typically goes wrong
   (this is gold for AI models)

### Category prefixes

Rules are named with category prefixes from
`_sections.md` for organization:

- `naming-conventions.md`
- `relationship-identifiers.md`
- `display-order-weight.md`

This makes it easy to find rules by domain and to add
new ones without renaming.

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

### Neglecting the description

A perfect SKILL.md body is useless if the description
doesn't trigger. After writing or updating a skill,
check whether the description covers the realistic
ways users ask for this task.
