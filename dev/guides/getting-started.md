# Getting Started

This guide walks you through installing and using
Infrahub skills with your AI coding assistant. By the
end, you will have the skills available in your
project and be able to invoke them to generate
schemas, data files, checks, and other Infrahub
artifacts following best practices.

Infrahub skills give AI assistants domain-specific
knowledge about Infrahub's data model, conventions,
and common pitfalls — producing higher-quality output
than general-purpose prompting alone.

## Prerequisites

- An AI coding assistant that supports skills
  ([Claude Code](https://docs.anthropic.com/en/docs/claude-code),
  GitHub Copilot, Cursor, Windsurf, or similar)
- An Infrahub repository to work with
  (or create one from scratch)

## Installation

### Option 1: npx (Recommended — Works Everywhere)

The `npx skills` CLI works with any AI tool that
supports the Agent Skills format:

```bash
# Add all Infrahub skills to your project
npx skills add opsmill/infrahub-skills

# Or add to a specific project directory
npx skills add opsmill/infrahub-skills \
  --path /path/to/your-infrahub-project
```

This downloads the skills into your project so any
AI assistant can discover them.

### Option 2: Claude Code Plugin (Marketplace)

If you use Claude Code, install as a plugin for
automatic availability across all your Infrahub
projects:

```bash
# Add the OpsMill marketplace
/plugin marketplace add opsmill/claude-marketplace

# Install the Infrahub plugin
/plugin install infrahub@opsmill
```

Or add directly to `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "opsmill": {
      "source": {
        "source": "github",
        "repo": "opsmill/claude-marketplace"
      }
    }
  },
  "enabledPlugins": {
    "infrahub@opsmill": true
  }
}
```

### Option 3: Claude Code Plugin (Git / Local)

```bash
# From git
git clone \
  https://github.com/opsmill/infrahub-skills.git
/plugin install ./infrahub-skills

# Or from a local path
/plugin install /path/to/infrahub-skills
```

### Option 4: Manual Copy

Copy the `skills/` directory into your project.
Always include `skills/infrahub-common/` — it contains shared
references that all skills depend on.

```bash
git clone \
  https://github.com/opsmill/infrahub-skills.git
cp -r infrahub-skills/skills \
  /path/to/your-infrahub-project/
rm -rf infrahub-skills
```

## How It Works

Skills follow the
[Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
format. Each skill is a directory with a `SKILL.md`
entry point and supporting files (rules, examples,
references). The AI assistant reads these files to
produce correct, best-practice Infrahub artifacts.

### Automatic Detection (Claude Code only)

When installed as a plugin, the SessionStart hook
automatically detects Infrahub projects by looking
for:

- `.infrahub.yml` or `infrahub.toml` configuration
  files
- Schema files containing `version: "1.0"` with
  `nodes:` or `generics:` keys

When detected, Claude is guided to use the appropriate
skill for each task.

### Manual Invocation

You can invoke skills directly by name:

```text
/infrahub:schema-creator
/infrahub:object-creator
/infrahub:check-creator
```

Or just describe your task — the AI will match it to
the right skill based on the description in the
SKILL.md frontmatter.

## Typical Workflow

A typical Infrahub project development flow follows
this order:

1. **Design the schema** — Define your data model
   (nodes, generics, attributes, relationships) using
   `infrahub:schema-creator`
2. **Populate data** — Create YAML data files for
   infrastructure objects with
   `infrahub:object-creator`
3. **Add validation** — Write Python checks that run
   in proposed change pipelines with
   `infrahub:check-creator`
4. **Build automation** — Create generators that
   produce objects from design definitions with
   `infrahub:generator-creator`
5. **Create transforms** — Convert Infrahub data to
   configs, reports, or exports with
   `infrahub:transform-creator`
6. **Customize the UI** — Design navigation menus for
   the web interface with `infrahub:menu-creator`
7. **Analyze data** — Query and correlate live
   Infrahub data with `infrahub:analyst`
8. **Audit** — Verify your repository follows best
   practices with `infrahub:repo-auditor`

Not every project needs every step. Schema and data
are the foundation; the rest depends on your use case.

## Available Skills

| Skill | Use When |
| ----- | -------- |
| `infrahub:schema-creator` | Designing data models — nodes, generics, attributes, relationships, hierarchies |
| `infrahub:object-creator` | Creating YAML data files — devices, locations, organizations, modules |
| `infrahub:check-creator` | Writing Python validation checks for proposed change pipelines |
| `infrahub:generator-creator` | Building design-driven automation (create objects from design definitions) |
| `infrahub:transform-creator` | Converting Infrahub data to other formats (JSON, text, CSV, device configs) |
| `infrahub:menu-creator` | Customizing the web UI sidebar with nested navigation menus |
| `infrahub:analyst` | Querying and correlating live Infrahub data via the MCP server |
| `infrahub:repo-auditor` | Auditing a repository against all rules and best practices |

## Using with Non-Claude Tools

These skills are plain Markdown — any AI tool that
reads files from your project can use them. See the
[README](../../README.md) for specific setup
instructions for GitHub Copilot, Cursor, and Windsurf.

## Verification

Confirm skills are installed and discoverable:

1. Check the skills directory exists in your project:

   ```bash
   ls skills/*/SKILL.md
   ```

   You should see one `SKILL.md` per skill (e.g.,
   `skills/infrahub-schema-creator/SKILL.md`).

2. Test a skill invocation — ask your AI assistant:

   ```text
   Create a simple Infrahub schema with a Device node
   that has a name and status attribute.
   ```

   The assistant should activate `infrahub:schema-creator`
   and produce a YAML schema starting with
   `version: "1.0"` containing a `nodes:` list.

3. For Claude Code plugin installs, verify detection:

   ```bash
   # In a directory with .infrahub.yml
   claude
   ```

   The SessionStart hook should report that Infrahub
   skills are available.

## Related Resources

- [Agent Skills specification](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
  — The format these skills follow
- [Infrahub documentation](https://docs.infrahub.app/)
  — Official Infrahub docs
- [README](../../README.md) — Project overview and
  setup for different AI tools
- [Adding a New Skill](./adding-a-skill.md)
  — Guide for contributing new skills
- [Running Evaluations](./running-evals.md)
  — How to test skill quality
