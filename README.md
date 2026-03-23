# Infrahub AI Skills

AI skills for developing with
[Infrahub](https://github.com/opsmill/infrahub),
the infrastructure data management platform by OpsMill.
These skills provide structured guidance — covering schema
design, data population, validation checks, generators,
transforms, and menu customization — to any AI coding
assistant that supports custom instructions or context files.

The skills are written in plain Markdown with lightweight
YAML frontmatter and are easy to adapt to whichever AI
tool you use.

## Installation

### Copy Skills into Your Repository

The simplest and most universal approach — works with
any AI tool. Copy the `skills/` directory into your
project so the AI assistant can discover the files
directly:

```bash
# Clone the skills repository
git clone https://github.com/opsmill/infrahub-skills.git

# Copy all skills into your Infrahub project
cp -r infrahub-skills/skills /path/to/your-infrahub-project/

# Clean up
rm -rf infrahub-skills
```

Or copy only the skills you need:

```bash
# Example: copy just schema and object creator skills
mkdir -p /path/to/your-infrahub-project/skills
cp -r infrahub-skills/skills/schema-creator /path/to/your-infrahub-project/skills/
cp -r infrahub-skills/skills/object-creator /path/to/your-infrahub-project/skills/
cp -r infrahub-skills/skills/common /path/to/your-infrahub-project/skills/
```

> **Note:** Always include `skills/common/` when copying
> individual skills — it contains shared references
> (GraphQL queries, `.infrahub.yml` format, git
> integration rules) that all skills depend on.

### Claude Code (Plugin)

If you prefer the plugin approach, the skills are
automatically available across all your Infrahub projects
without copying files into each one.

#### Option 1: Via OpsMill Marketplace (Recommended)

Run these commands inside Claude Code:

```bash
# Add the OpsMill marketplace
/plugin marketplace add opsmill/claude-marketplace

# Install the Infrahub plugin from the marketplace
/plugin install infrahub@opsmill
```

Or add to your `~/.claude/settings.json`:

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

#### Option 2: Via Git

Clone and install directly from the repository:

```bash
# Clone the repository
git clone https://github.com/opsmill/infrahub-skills.git

# Install the plugin (run inside Claude Code)
/plugin install ./infrahub-skills
```

#### Option 3: Local Path

If you have the plugin locally, run inside Claude Code:

```bash
/plugin install /path/to/infrahub-skills
```

## Skills

### Schema Creator

**Name:** `infrahub-schema-creator`

Create, validate, and modify Infrahub schemas for
infrastructure data management.

**Capabilities:**

- Create new schemas from natural language requirements
- Design nodes with attributes, relationships, and generics
- Set up hierarchical location trees and component/parent patterns
- Configure display properties (human_friendly_id, display_label)
- Validate schemas and plan migrations

**Documentation:** `skills/schema-creator/` --
SKILL.md, reference.md, examples.md, validation.md,
rules/

---

### Object Creator

**Name:** `infrahub-object-creator`

Create and manage Infrahub object data files for
populating infrastructure data.

**Capabilities:**

- Create YAML data files for devices, locations, organizations, modules
- Set up hierarchical data (location trees, tenant groups)
- Reference related objects across files
- Manage component children (interfaces, modules, bays)
- Organize files for correct dependency load order

**Documentation:** `skills/object-creator/` --
SKILL.md, reference.md, examples.md, rules/

---

### Check Creator

**Name:** `infrahub-check-creator`

Create validation checks that run in proposed change
pipelines.

**Capabilities:**

- Write Python validation logic (InfrahubCheck class)
- Create GraphQL queries for data fetching
- Build global and targeted checks
- Register checks in .infrahub.yml
- Debug check failures

**Documentation:** `skills/check-creator/` --
SKILL.md, examples.md, rules/

---

### Generator Creator

**Name:** `infrahub-generator-creator`

Create design-driven generators that automatically
create infrastructure objects.

**Capabilities:**

- Build generators that create objects from design definitions
- Implement idempotent create-or-update workflows (allow_upsert)
- Set up target groups and GraphQL queries
- Configure automatic cleanup of stale objects
- Register generators in .infrahub.yml

**Documentation:** `skills/generator-creator/` --
SKILL.md, examples.md, rules/

---

### Transform Creator

**Name:** `infrahub-transform-creator`

Create data transforms that convert Infrahub data into
different formats.

**Capabilities:**

- Build Python transforms (InfrahubTransform class)
- Create Jinja2 template-based transforms
- Generate device configs, CSV reports, inventory exports
- Connect transforms to artifacts for automated output
- Hybrid Python + Jinja2 patterns

**Documentation:** `skills/transform-creator/` --
SKILL.md, examples.md, rules/

---

### Menu Creator

**Name:** `infrahub-menu-creator`

Create custom navigation menus for the Infrahub web
interface.

**Capabilities:**

- Design navigation menus with nested hierarchies
- Organize node types into logical groups
- Configure icons (MDI icon set) and labels
- Link menu items to schema node list views

**Documentation:** `skills/menu-creator/` --
SKILL.md, rules/

---

### Analyst

**Name:** `infrahub-analyst`

Analyze and correlate live Infrahub data using the MCP server to answer operational questions on demand.

**Capabilities:**
- Answer operational questions interactively ("which devices are in tonight's maintenance window?")
- Correlate data across multiple node types (services, BGP sessions, prefixes, devices)
- Investigate service impact and blast radius before a change
- Detect drift between design intent and realized objects
- Audit data quality (naming, IP space, missing attributes)
- Produce one-off reports for stakeholders

**Requires:** Infrahub MCP server connected to Claude

**Documentation:** `skills/analyst/` -- SKILL.md, examples.md, rules/

---

### Common References

Shared documentation and rules referenced by all skills.

**Contents:**

- `graphql-queries.md` -- GraphQL query writing reference
- `infrahub-yml-reference.md` -- .infrahub.yml project configuration
- `rules/` -- Shared rules (git integration, caching gotchas)

**Location:** `skills/common/`

## Using with Other AI Tools

These skills follow the
[Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
format — each skill is a directory with a `SKILL.md`
entry point (with `name` and `description` frontmatter)
plus supporting reference files. Any AI coding tool that
supports skills can use them directly.

For tools that don't support skills natively, copy the
`skills/` directory into your project and point the tool
at the relevant files.

### GitHub Copilot

Copy the `skills/` directory into your repo, then
reference the skills from a Copilot instructions file:

```bash
cp -r skills/ /path/to/your-infrahub-project/skills/
```

Create `.github/instructions/infrahub.instructions.md`
to point Copilot at the skills:

```markdown
---
applyTo: '**/*.py,**/*.yml,**/*.yaml'
---
For Infrahub development guidance, refer to the skill files in skills/.
```

See [GitHub Copilot custom instructions docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions).

### Cursor

Copy the `skills/` directory into your repo, then
create a Cursor rule to reference them:

```bash
cp -r skills/ /path/to/your-infrahub-project/skills/
```

Create `.cursor/rules/infrahub.mdc`:

```markdown
---
description: Infrahub development guidance
globs: ["**/*.py", "**/*.yml", "**/*.yaml"]
alwaysApply: false
---
For Infrahub development guidance, refer to the skill files in skills/.
```

See [Cursor Rules docs](https://cursor.com/docs/context/rules).

### Windsurf

Copy the `skills/` directory into your repo. Windsurf
will pick up the Markdown files as context. You can also
reference them from `.windsurfrules` at your project
root.

See [Windsurf Rules docs](https://docs.windsurf.com/windsurf/customize#rules).

### Other AI Tools

For any AI coding tool:

1. Copy the `skills/` directory into your project
2. If the tool supports skills natively, it should
   discover the `SKILL.md` files automatically
3. Otherwise, point the tool's context or instructions
   configuration at the relevant `SKILL.md` files —
   each one references supporting files
   (`reference.md`, `examples.md`, `rules/`) for
   detailed guidance

---

## Automatic Detection (Claude Code only)

The Claude Code plugin automatically detects Infrahub
projects on session start by looking for:

- `.infrahub.yml` or `infrahub.toml` configuration files
- Schema files with `version: "1.0"` and `nodes:` or `generics:` keys

When detected, Claude is instructed to use the
appropriate skills for relevant tasks.

## Project Structure

```text
.
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   └── hooks.json               # Hook definitions
├── hooks-handlers/
│   └── session-start.sh         # Infrahub project detection script
├── skills/
│   ├── common/                  # Shared references and rules
│   │   ├── graphql-queries.md
│   │   ├── infrahub-yml-reference.md
│   │   └── rules/
│   ├── schema-creator/          # Schema design skill
│   ├── object-creator/          # Data population skill
│   ├── check-creator/           # Validation check skill
│   ├── generator-creator/       # Generator automation skill
│   ├── transform-creator/       # Data transform skill
│   ├── menu-creator/            # Navigation menu skill
│   └── analyst/                 # MCP-based data analysis skill
├── CLAUDE.md                    # Project context
├── README.md                    # This file
└── LICENSE                      # Apache 2.0 License
```

## Resources

- [Infrahub Documentation](https://docs.infrahub.app/)
- [Infrahub Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Schema Library](https://github.com/opsmill/schema-library)
- [OpsMill](https://opsmill.com/)

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
