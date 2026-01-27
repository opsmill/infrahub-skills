# CLAUDE.md - Project Context

This file provides context for Claude when working with this Infrahub plugin project.

## Project Overview

This is a Claude Code plugin for [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill. The plugin provides skills to help users design, create, validate, and modify Infrahub schemas.

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
│   └── schema-creator/
│       ├── SKILL.md             # Main skill definition
│       ├── reference.md         # Schema property reference
│       ├── validation.md        # Validation and migration guide
│       └── examples.md          # Example schema templates
├── CLAUDE.md                    # This file - project context
├── README.md                    # User documentation
└── LICENSE                      # MIT License
```

## Skills

### Schema Creator (`infrahub-schema-creator`)

Located in `skills/schema-creator/`. Helps users create and manage Infrahub schemas.

**Files:**
- `SKILL.md` - Entry point with overview, capabilities, and quick start
- `reference.md` - Complete reference for nodes, attributes, relationships, generics
- `validation.md` - Commands for validating/loading schemas, migration strategies
- `examples.md` - Ready-to-use schema templates (IPAM, VLANs, datacenter, etc.)

## Development Guidelines

### Adding New Skills

1. Create a new directory in `skills/` (e.g., `skills/my-skill/`)
2. Add a `SKILL.md` file with required YAML frontmatter:
   ```yaml
   ---
   name: my-skill-name
   description: Brief description of what this skill does
   ---
   ```
3. Include sections: Description, Capabilities, When to Use
4. Add supporting `.md` files for detailed reference content
5. Keep `SKILL.md` under 500 lines; use linked files for extended content

### Modifying Schema Creator

- Keep best practices in `reference.md`
- Add new examples to `examples.md`
- Update validation commands in `validation.md`
- Ensure `SKILL.md` links to all supporting files

## Conventions

- Use semantic versioning for plugin versions
- Skills require YAML frontmatter with `name` and `description`
- Skill names: lowercase with hyphens (e.g., `infrahub-schema-creator`)
- Keep documentation current with Infrahub schema format changes

## Resources

- [Infrahub Documentation](https://docs.infrahub.app/)
- [Infrahub Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Schema Library](https://github.com/opsmill/schema-library)
- [Claude Code Plugin Documentation](https://docs.anthropic.com/en/docs/claude-code)
