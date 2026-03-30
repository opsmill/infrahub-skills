# Adding a New Skill

## Overview

Each skill lives in its own directory under `skills/`
and provides AI assistants with domain-specific rules,
examples, and references for a particular Infrahub
development task. Skills follow the
[Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
format.

## Skill Anatomy

```text
skills/infrahub-my-skill/
├── SKILL.md              # Entry point (required)
├── examples.md           # Ready-to-use patterns
├── reference.md          # Property/format reference
└── rules/                # Modular rules by category
    ├── _sections.md      # Category index
    ├── _template.md      # Template for new rules
    ├── 01-naming-foo.md  # Individual rule files
    └── 02-structure-bar.md
```

### Progressive Disclosure

Skills use a three-level loading system to manage
context window usage:

1. **Metadata** (name + description in frontmatter)
   — Always visible to the AI (~100 words). This is
   what determines whether the skill triggers.
2. **SKILL.md body** — Loaded when the skill activates
   (<500 lines ideal). Contains the overview, workflow,
   and pointers to supporting files.
3. **Supporting files** (rules, examples, references)
   — Loaded on demand as the AI works through the
   task. No size limit, but keep individual files
   focused.

The key insight: SKILL.md should tell the AI *what to
do and where to look*, not contain everything.
Individual rule files and references hold the details.

## Prerequisites

- Access to this repository and permission to create
  branches/PRs
- Familiarity with core Infrahub concepts (schemas,
  nodes, generics, relationships) — see
  [infrahub-concepts.md](../knowledges/infrahub-concepts.md)
- A text editor with YAML/Markdown support
- Access to Claude Code (or another AI assistant that
  supports skills) for testing
- Basic understanding of the skill format — review
  the [Skill Anatomy](#skill-anatomy) section below

## Steps

### 1. Create the Skill Directory

```bash
mkdir -p skills/infrahub-my-skill/rules
```

- Directory name matches the skill name
  (e.g., `infrahub-schema-creator`)
- Skill name in frontmatter uses the same name
  (e.g., `infrahub-schema-creator`)

### 2. Write SKILL.md

Start with the YAML frontmatter — this is the
primary triggering mechanism:

```yaml
---
name: infrahub-my-skill
description: >-
  Create and manage Infrahub [thing].
  Use when [specific contexts].
  TRIGGER when: [what the user says or does].
  DO NOT TRIGGER when: [what might look similar
  but isn't].
metadata:
  version: 1.1.0
  author: OpsMill
---
```

**Writing the description**: The description determines
when the AI activates the skill. Be specific about
trigger contexts. Today's AI tools tend to
*under-trigger* skills, so lean toward being slightly
"pushy" — mention the key phrases a user would say,
including synonyms and adjacent concepts.

**Body sections to include**:

- **Overview** — 1-2 paragraphs on what the skill does
- **When to Use** — Concrete trigger conditions
- **Workflow** — Numbered steps the AI should follow
- **Rule Categories** — Links to `rules/_sections.md`
  or directly to rule files
- **Supporting References** — When to read
  `examples.md`, `reference.md`, `../infrahub-common/`
  resources

**Writing tips** (from the skill-creator best
practices):

- Explain the *why* behind instructions, not just
  the *what*. AI models respond better to reasoning
  than rigid commands.
- If you find yourself writing ALWAYS or NEVER in
  caps, reframe as an explanation of *why it matters*.
- Use the imperative form for instructions ("Check
  the namespace", not "You should check the
  namespace").
- Include examples inline for critical patterns —
  models learn from examples more reliably than from
  abstract rules.

### 3. Add Rules

Rules are modular, individually addressable best
practices. Each rule file covers one specific concern.

**Create `rules/_sections.md`** to define the category
index:

```markdown
## Rule Categories

| Prefix | Category | Description |
| -------- | ---------- | ------------- |
| naming | Naming | Naming conventions and constraints |
| structure | Structure | Structural requirements and patterns |
| display | Display | UI display configuration |
```

**Create individual rules** using
`rules/_template.md` as a starting point. Each rule
should have:

- A clear title and one-sentence summary
- **Why it matters** — the reasoning behind the rule
- **The rule** — what to check or enforce
- **Examples** — compliant and non-compliant patterns
- **Common mistakes** — what the AI (or user)
  typically gets wrong

### 4. Add Supporting Files

- **`examples.md`** — Ready-to-use patterns the AI
  can adapt. These are high-value: models learn from
  concrete examples more reliably than abstract
  instructions. Include 2-3 complete, realistic
  examples covering different complexity levels.
- **`reference.md`** — Property/format reference
  tables. Useful when the skill deals with structured
  formats (schema properties, YAML fields, API
  parameters).
- **`../infrahub-common/`** — Reference shared resources for
  cross-cutting concerns:
  - `graphql-queries.md` — Query syntax for checks,
    generators, transforms
  - `infrahub-yml-reference.md` — `.infrahub.yml`
    configuration format
  - `rules/` — Shared rules (git integration,
    display label caching)

### 5. Update Version Tracking

The skill's `metadata.version` in SKILL.md must match:

1. `.claude-plugin/plugin.json` (`version` field)
2. `.github/.release-manifest.json` (`version` field)

Add the skill name to the `skills` array in
`.github/.release-manifest.json`.

### 6. Write Evaluations

Add evaluation tasks to the root `eval.yaml` and
create deterministic grader scripts in
`graders/my-skill/` to test the skill produces
correct output.

```yaml
skill_name: infrahub-my-skill

tasks:
  - id: basic-scenario
    prompt: >-
      A realistic user request with specific names,
      namespaces, and field types.
    expected_output: >-
      What correct output looks like.
    grader: graders/my-skill/basic-scenario.sh

  - id: advanced-scenario
    prompt: >-
      A more complex request covering relationships
      or edge cases.
    expected_output: >-
      What correct output looks like.
    grader: graders/my-skill/advanced-scenario.sh
```

Each grader script in `graders/my-skill/` reads the model
output on stdin and prints `{"pass": true}` or
`{"pass": false, "reason": "..."}` to stdout.

**Writing good eval prompts**: Make them realistic —
the kind of thing an actual user would type, with
specific details (names, namespaces, field types).
Not abstract requests like "create a schema" but
concrete ones like "Create an Infrahub schema for a
VLAN management system with...".

**Writing good assertions**: Each grader should be
objectively deterministic. Use descriptive file names
that explain what's being tested at a glance (e.g.,
`dropdown-for-status.sh` not `check-1.sh`).

Run evals with skillgrade to iterate on quality:

```bash
skillgrade --smoke
```

### 7. Register in Documentation

- Add the skill to the table in `CLAUDE.md`
- Add the skill to `README.md`
  (skills section + project structure)
- Update `CHANGELOG.md`
- Update `AGENTS.md` quick reference table

### 8. Verification

Confirm the skill works before submitting for review.

**Test skill triggering:**

1. Open a project with the plugin installed
2. Describe a task that should activate the skill
3. Verify the AI reads your SKILL.md and follows the
   workflow

**Verify output correctness:**

1. Run the skill against a realistic prompt
2. Check the output against the rules in your
   `rules/` directory
3. Validate any generated YAML with
   `infrahubctl schema check` (for schema skills) or
   equivalent tooling

**Run evaluations** (see [Step 6](#6-write-evaluations)):

```bash
skillgrade --smoke
```

Review results with `skillgrade preview`.

**Required files checklist:**

- [ ] `skills/infrahub-my-skill/SKILL.md` with correct
  frontmatter
- [ ] `skills/infrahub-my-skill/rules/_sections.md`
- [ ] At least one rule file in `rules/`
- [ ] Tasks added to root `eval.yaml`
- [ ] `graders/my-skill/` with grader scripts
- [ ] `CLAUDE.md` updated with the new skill
- [ ] `README.md` updated (skills section + project
  structure)
- [ ] `CHANGELOG.md` updated
- [ ] `AGENTS.md` quick reference table updated
  (see [Step 7](#7-register-in-documentation))

**Validate version consistency:**

Verify the `metadata.version` in your SKILL.md
matches the versions in:

- `.claude-plugin/plugin.json`
- `.github/.release-manifest.json`

All three must be identical.
