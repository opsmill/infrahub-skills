# Infrahub AI Skills

AI skills for developing with [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill. These skills provide structured guidance — covering schema design, data population, validation checks, generators, transforms, and menu customization — to any AI coding assistant that supports custom instructions or context files.

The skills are written in plain Markdown with lightweight YAML frontmatter and are easy to adapt to whichever AI tool you use.

## Installation

### Claude Code (Plugin)

#### Option 1: Via OpsMill Marketplace (Recommended)

Add the OpsMill Claude marketplace, then install the plugin. Run these commands inside Claude Code:

```bash
# Add the OpsMill marketplace
/plugin marketplace add opsmill/opsmill-claude-marketplace

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
        "repo": "opsmill/opsmill-claude-marketplace"
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
git clone https://github.com/opsmill/infrahub-claude-plugin.git

# Install the plugin (run inside Claude Code)
/plugin install ./infrahub-claude-plugin
```

#### Option 3: Local Path

If you have the plugin locally, run inside Claude Code:

```bash
/plugin install /path/to/infrahub-claude-plugin
```

## Skills

### Schema Creator

**Name:** `infrahub-schema-creator`

Create, validate, and modify Infrahub schemas for infrastructure data management.

**Capabilities:**
- Create new schemas from natural language requirements
- Design nodes with attributes, relationships, and generics
- Set up hierarchical location trees and component/parent patterns
- Configure display properties (human_friendly_id, display_label)
- Validate schemas and plan migrations

**Documentation:** `skills/schema-creator/` -- SKILL.md, reference.md, examples.md, validation.md, rules/

---

### Object Creator

**Name:** `infrahub-object-creator`

Create and manage Infrahub object data files for populating infrastructure data.

**Capabilities:**
- Create YAML data files for devices, locations, organizations, modules
- Set up hierarchical data (location trees, tenant groups)
- Reference related objects across files
- Manage component children (interfaces, modules, bays)
- Organize files for correct dependency load order

**Documentation:** `skills/object-creator/` -- SKILL.md, reference.md, examples.md, rules/

---

### Check Creator

**Name:** `infrahub-check-creator`

Create validation checks that run in proposed change pipelines.

**Capabilities:**
- Write Python validation logic (InfrahubCheck class)
- Create GraphQL queries for data fetching
- Build global and targeted checks
- Register checks in .infrahub.yml
- Debug check failures

**Documentation:** `skills/check-creator/` -- SKILL.md, examples.md, rules/

---

### Generator Creator

**Name:** `infrahub-generator-creator`

Create design-driven generators that automatically create infrastructure objects.

**Capabilities:**
- Build generators that create objects from design definitions
- Implement idempotent create-or-update workflows (allow_upsert)
- Set up target groups and GraphQL queries
- Configure automatic cleanup of stale objects
- Register generators in .infrahub.yml

**Documentation:** `skills/generator-creator/` -- SKILL.md, examples.md, rules/

---

### Transform Creator

**Name:** `infrahub-transform-creator`

Create data transforms that convert Infrahub data into different formats.

**Capabilities:**
- Build Python transforms (InfrahubTransform class)
- Create Jinja2 template-based transforms
- Generate device configs, CSV reports, inventory exports
- Connect transforms to artifacts for automated output
- Hybrid Python + Jinja2 patterns

**Documentation:** `skills/transform-creator/` -- SKILL.md, examples.md, rules/

---

### Menu Creator

**Name:** `infrahub-menu-creator`

Create custom navigation menus for the Infrahub web interface.

**Capabilities:**
- Design navigation menus with nested hierarchies
- Organize node types into logical groups
- Configure icons (MDI icon set) and labels
- Link menu items to schema node list views

**Documentation:** `skills/menu-creator/` -- SKILL.md, rules/

---

### Common References

Shared documentation and rules referenced by all skills.

**Contents:**
- `graphql-queries.md` -- GraphQL query writing reference
- `infrahub-yml-reference.md` -- .infrahub.yml project configuration
- `rules/` -- Shared rules (git integration, caching gotchas)

**Location:** `skills/common/`

## Using with Other AI Tools

The skill content in this repository is plain Markdown — any AI coding assistant that supports custom instructions or context files can benefit from it. The YAML frontmatter in each `SKILL.md` is Claude Code-specific metadata; other tools can ignore or strip it.

Clone the repository and point your tool at the relevant skill files as described below.

### GitHub Copilot

Copilot supports both a single repo-wide file and per-path instruction files with YAML frontmatter.

- **Repo-wide:** Copy the content of the relevant `SKILL.md` files (without the frontmatter) into `.github/copilot-instructions.md`.
- **Per-path (recommended):** Create `.github/instructions/infrahub-<skill>.instructions.md` files using Copilot's frontmatter format, then paste in the skill content:

  ```markdown
  ---
  applyTo: '**/*.py,**/*.yml,**/*.yaml'
  ---
  <!-- skill content here -->
  ```

See [GitHub Copilot custom instructions docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions).

### Cursor

Cursor uses `.cursor/rules/*.mdc` files (the old `.cursorrules` format is deprecated). The `.mdc` format is YAML frontmatter + Markdown, which maps directly to the skill files here.

Copy each skill's content into `.cursor/rules/infrahub-<skill>.mdc`, replacing the Claude-specific frontmatter with Cursor's:

```markdown
---
description: Infrahub schema design guidance
globs: ["**/*.yml", "**/*.yaml"]
alwaysApply: false
---
<!-- skill content here -->
```

See [Cursor Rules docs](https://cursor.com/docs/context/rules).

---

## Automatic Detection (Claude Code only)

The Claude Code plugin automatically detects Infrahub projects on session start by looking for:
- `.infrahub.yml` or `infrahub.toml` configuration files
- Schema files with `version: "1.0"` and `nodes:` or `generics:` keys

When detected, Claude is instructed to use the appropriate skills for relevant tasks.

## Project Structure

```
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
│   └── menu-creator/            # Navigation menu skill
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
