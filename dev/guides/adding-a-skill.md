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
  (e.g., `infrahub-managing-schemas`)
- Skill name in frontmatter uses the same name
  (e.g., `infrahub-managing-schemas`)

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

The skill's `metadata.version` in SKILL.md must match
the current release version, which lives in five files
— see [../guidelines/versioning.md](../guidelines/versioning.md).
For a new skill, copy the version already in
`.claude-plugin/plugin.json` rather than bumping
anything.

Add the skill name to the `skills` array in
`.github/.release-manifest.json`. That array is what the
published release claims to ship; a skill missing from
it is not in the release.

### 6. Write Evaluations

Add evaluation tasks to the root `eval.yaml` and
create deterministic grader scripts in
`graders/my-skill/` to test the skill produces
correct output.

Each task names the skill to load in its own
`instruction`, which is how tasks for different skills
coexist in one file:

```yaml
tasks:
  - name: basic-scenario
    trials: 3
    instruction: |
      Read the skill at .agents/skills/infrahub-my-skill/SKILL.md
      and follow its workflow and rules.

      A realistic user request with specific names,
      namespaces, and field types.

      Save ONLY the final YAML to: output.yml
    graders:
      - type: deterministic
        run: python graders/my-skill/check_basic_scenario.py
        weight: 1.0
    expected_output: >-
      What correct output looks like.

  - name: advanced-scenario
    trials: 3
    instruction: |
      Read the skill at .agents/skills/infrahub-my-skill/SKILL.md
      and follow its workflow and rules.

      A more complex request covering relationships
      or edge cases.

      Save ONLY the final YAML to: output.yml
    graders:
      - type: deterministic
        run: python graders/my-skill/check_advanced_scenario.py
        weight: 1.0
    expected_output: >-
      What correct output looks like.
```

`graders` is what skillgrade scores, by weight. The
full task shape, including the `expectations` and
`assertions` blocks that document a task without
failing a run, is in
[running-evals.md](./running-evals.md#evalyaml-format).

Each grader script in `graders/my-skill/` calls the
shared `run_checks` library and prints the result as
JSON to stdout. See
[adding-a-rule.md](./adding-a-rule.md#4-add-a-task-grader-script)
for the script shape.

**Writing good eval prompts**: Make them realistic —
the kind of thing an actual user would type, with
specific details (names, namespaces, field types).
Not abstract requests like "create a schema" but
concrete ones like "Create an Infrahub schema for a
VLAN management system with...".

**Writing good assertions**: Each grader should be
objectively deterministic. Use descriptive file names
that explain what's being tested at a glance (e.g.,
`check_dropdown_for_status.py` not `check_1.py`).

Run evals with skillgrade to iterate on quality:

```bash
skillgrade --smoke
```

After editing `eval.yaml`, regenerate the JSON
projection used by the `/skill-creator` evals
runner:

```bash
python scripts/sync-evals.py
```

Commit the regenerated `evaluations/*.json` files
alongside the `eval.yaml` change.

For the per-rule eval workflow (the more common
case once a skill exists), see
[adding-a-rule.md](./adding-a-rule.md).

### 7. Register in Documentation

Five surfaces, none of them checked by CI. The list and
what to add to each is in
[../guidelines/skill-registration.md](../guidelines/skill-registration.md),
which loads on its own when you edit a `SKILL.md`.

Apply the appropriate `type/*` and `changes/*` labels to
your PR so [release-drafter](../../.github/release-drafter.yml)
files it in the right category. The drafted body is a
starting point, not the release notes: each release also
gets a curated page under `docs/docs/release-notes/`,
per the same rule.

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
- [ ] `python scripts/sync-evals.py` run and the
  regenerated `evaluations/*.json` committed
- [ ] `CLAUDE.md` updated with the new skill
- [ ] `README.md` updated (skills section + project
  structure)
- [ ] `AGENTS.md` quick reference table updated
  (see [Step 7](#7-register-in-documentation))
- [ ] PR labeled with `type/*` and `changes/*` so
  release-drafter categorizes it correctly

**Validate version consistency:**

Verify the `metadata.version` in your SKILL.md
matches the versions in:

- `.claude-plugin/plugin.json`
- `.github/.release-manifest.json`

All three must be identical.
