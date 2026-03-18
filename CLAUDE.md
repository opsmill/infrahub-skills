# CLAUDE.md - Project Context

This file provides context for Claude when working with this Infrahub plugin project.

## Project Overview

This is a Claude Code plugin for [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill. The plugin provides skills covering the full Infrahub development lifecycle: schema design, data population, validation checks, generators, transforms, and menu customization.

## Directory Structure

```
.
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest (required)
├── hooks/
│   └── hooks.json               # Hook definitions (SessionStart detection)
├── hooks-handlers/
│   └── session-start.sh         # Detects Infrahub projects and activates skills
├── skills/
│   ├── common/                  # Shared references and rules
│   │   ├── graphql-queries.md   # GraphQL query writing reference
│   │   ├── infrahub-yml-reference.md  # .infrahub.yml config reference
│   │   └── rules/              # Shared rules (git integration, caching)
│   ├── schema-creator/          # Schema design skill
│   ├── object-creator/          # Data population skill
│   ├── check-creator/           # Validation check skill
│   ├── generator-creator/       # Generator automation skill
│   ├── transform-creator/       # Data transform skill
│   ├── menu-creator/            # Navigation menu skill
│   └── repo-auditor/            # Repository audit skill
├── .github/
│   └── .release-manifest.json   # Centralized version tracking
├── CLAUDE.md                    # This file - project context
├── CHANGELOG.md                 # Version history (Keep-a-Changelog format)
├── README.md                    # User documentation
└── LICENSE                      # Apache 2.0 License
```

## Skills

| Skill | Directory | Description |
|-------|-----------|-------------|
| `infrahub-schema-creator` | `skills/schema-creator/` | Schema nodes, generics, attributes, relationships |
| `infrahub-object-creator` | `skills/object-creator/` | YAML data files for infrastructure objects |
| `infrahub-check-creator` | `skills/check-creator/` | Python validation checks for proposed changes |
| `infrahub-generator-creator` | `skills/generator-creator/` | Design-driven automation (create objects from designs) |
| `infrahub-transform-creator` | `skills/transform-creator/` | Data transforms (Python/Jinja2 to JSON/text/CSV) |
| `infrahub-menu-creator` | `skills/menu-creator/` | Custom navigation menus for the web UI |
| `infrahub-repo-auditor` | `skills/repo-auditor/` | Audit repository against all rules and best practices |

Each skill directory contains:
- `SKILL.md` - Entry point with overview, capabilities, rule categories
- `examples.md` - Ready-to-use patterns (most skills)
- `reference.md` - Property/format reference (schema-creator, object-creator)
- `rules/` - Individual rules organized by category prefix with `_sections.md` index
- `evals/evals.json` - Evaluation scenarios (skill-creator format, run via `/skill-creator`)

## Shared Resources (`skills/common/`)

- `graphql-queries.md` - GraphQL query syntax for checks, generators, transforms
- `infrahub-yml-reference.md` - .infrahub.yml project configuration
- `rules/` - Cross-cutting rules (git integration, display label caching)

## Development Guidelines

### Adding New Skills

1. Create a new directory in `skills/` (e.g., `skills/my-skill/`)
2. Add a `SKILL.md` file with required YAML frontmatter:
   ```yaml
   ---
   name: infrahub-my-skill
   description: Brief description of what this skill does
   metadata:
     version: 1.1.0
     author: OpsMill
   ---
   ```
3. Include sections: Overview, When to Use, Rule Categories, Supporting References
4. Add a `rules/` directory with `_sections.md` and `_template.md`
5. Add supporting `.md` files for detailed reference content
6. Keep `SKILL.md` under 500 lines; use linked files for extended content
7. Reference `../common/` for shared resources

### Adding New Rules

- Skill-specific rules go in `skills/<skill>/rules/` with the category prefix from `_sections.md`
- Cross-cutting rules (apply to multiple skills) go in `skills/common/rules/`
- Follow the template format in `rules/_template.md`

## Conventions

- Use semantic versioning for plugin versions
- All skills share a unified version matching `plugin.json` — when bumping, update all three locations together:
  1. `.claude-plugin/plugin.json` (`version` field)
  2. `.github/.release-manifest.json` (`version` field)
  3. Every `skills/*/SKILL.md` (`metadata.version` in frontmatter)
- Skills require YAML frontmatter with `name`, `description`, and `metadata` (version + author)
- Skill names: `infrahub-` prefix with lowercase hyphens (e.g., `infrahub-schema-creator`)
- Directory names: drop the `infrahub-` prefix (e.g., `schema-creator/`)
- Keep documentation current with Infrahub schema format changes
- Document notable changes in `CHANGELOG.md` using Keep-a-Changelog format

## Resources

- [Infrahub Documentation](https://docs.infrahub.app/)
- [Infrahub Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Schema Library](https://github.com/opsmill/schema-library)
- [Claude Code Plugin Documentation](https://docs.anthropic.com/en/docs/claude-code)
