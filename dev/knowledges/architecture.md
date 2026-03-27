# Architecture Overview

## System Design

This repository is a **Claude Code plugin** — a
collection of Markdown-based skills that provide
domain-specific guidance to AI coding assistants when
working with Infrahub repositories. It contains no
Python code; all guidance is expressed as structured
Markdown documents.

### Key Concepts

| Concept | Description |
| ------- | ----------- |
| **Plugin** | A packaged set of skills, hooks, and metadata distributed via `.claude-plugin/plugin.json` |
| **Skill** | A self-contained unit of domain knowledge with rules, examples, and references |
| **Rule** | An individual best practice or requirement within a skill, organized by category prefix |
| **Hook** | A trigger that detects project context and activates skills automatically |
| **Evaluation** | A test scenario that verifies a skill produces correct output |

## Component Architecture

```text
Plugin (plugin.json)
├── Hooks (hooks/hooks.json)
│   └── SessionStart → hooks-handlers/session-start.sh
│       └── Detects .infrahub.yml, infrahub.toml,
│           schema files
│
├── Skills (skills/)
│   ├── schema-creator/
│   │   ├── SKILL.md          ← Entry point
│   │   ├── rules/            ← Modular rules
│   │   │   ├── _sections.md  ← Category index
│   │   │   └── *.md          ← Individual rules
│   │   ├── examples.md       ← Ready-to-use patterns
│   │   ├── reference.md      ← Property/format tables
│   │   └── validation.md     ← Validation guidance
│   │
│   ├── object-creator/
│   ├── check-creator/
│   ├── generator-creator/
│   ├── transform-creator/
│   ├── menu-creator/
│   ├── repo-auditor/
│   │
│   └── common/               ← Cross-cutting refs
│       ├── graphql-queries.md
│       ├── infrahub-yml-reference.md
│       └── rules/            ← Shared rules
│
├── eval.yaml                             ← skillgrade config (all skills)
│
└── graders/                              ← Deterministic grader scripts
    ├── schema-creator/                   ← schema-creator graders
    └── menu-creator/                     ← menu-creator graders
```

## Progressive Disclosure Model

Skills use a three-level loading system designed to
manage AI context window efficiently:

```text
Level 1: Metadata (always loaded, ~100 words)
  ├── name: "infrahub-schema-creator"
  └── description: "Create and validate..."
         ↓ triggers activation
Level 2: SKILL.md body (loaded on activation)
  ├── Overview, workflow, rule categories
  └── Pointers to Level 3 files
         ↓ loaded on demand
Level 3: Supporting files (loaded as needed)
  ├── rules/*.md — individual rules
  ├── examples.md — complete patterns
  ├── reference.md — property tables
  └── ../common/*.md — shared references
```

The description field in the frontmatter is the
primary triggering mechanism — it determines whether
the AI activates the skill at all. SKILL.md tells the
AI what to do and where to look. Supporting files
provide the actual details.

## Rule System

Each skill organizes its rules using a consistent
structure:

- **`_sections.md`** — Defines category prefixes and
  serves as the table of contents
- **`_template.md`** — Template for creating new rules
  with consistent structure
- **Individual rule files** — Named with category
  prefix (e.g., `naming-conventions.md`,
  `relationship-identifiers.md`)

Rules are designed to be independently addressable —
the AI reads only the rules relevant to the current
task, keeping context focused.

## Evaluation System

Evaluations test that skills produce correct output.
Each skill that has evals carries them alongside its
other files:

- **`eval.yaml`** — Single skillgrade configuration at
  project root defining all tasks with prompts,
  expected output descriptions, and grader script paths
- **`graders/`** — Deterministic Python scripts
  organized per skill that read model output and emit
  skillgrade JSON

Run evals locally with skillgrade:

```bash
skillgrade --smoke
```

CI runs `skillgrade --ci --provider=local --threshold=0.8`
per skill in a matrix, failing if the pass rate drops
below the threshold. The eval workflow: run prompts,
grade outputs with graders, view results with
`skillgrade preview`, and refine the skill based on
failures.

## Design Decisions

### Pure Markdown, No Code

All guidance is Markdown. This keeps the plugin
lightweight, easy to review, version-controlled with
meaningful diffs, and portable across AI tools
(not just Claude Code).

### Rule-Based Skills Over Monolithic Prompts

Breaking skills into modular rules (rather than one
large prompt) means:

- Rules can be loaded selectively, saving context
  window
- Individual rules can be tested and improved
  independently
- New rules can be added without refactoring existing
  ones
- The `_sections.md` index makes the structure
  navigable

### Shared Common Resources

Cross-cutting concerns live in `skills/common/` to
avoid duplication. When multiple skills need GraphQL
query guidance or `.infrahub.yml` format reference,
they point to the same shared files.

### Automatic Detection via Hooks

The SessionStart hook (`hooks-handlers/session-start.sh`)
checks for Infrahub project markers and provides skill
activation context, making the plugin
zero-configuration for users. Detection looks for:

- `.infrahub.yml` or `infrahub.toml` config files
- Schema files with `version: "1.0"` and `nodes:` or
  `generics:` keys

### Agent Skills Format

Following the
[Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
format means the skills work not just with Claude Code
but with any AI tool that supports the format, or can
be manually copied into projects for tools that read
Markdown files.
