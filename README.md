# Infrahub Claude Code Plugin

A Claude Code plugin for developing with [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill.

## Installation

### Option 1: Via OpsMill Marketplace (Recommended)

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

### Option 2: Via Git

Clone and install directly from the repository:

```bash
# Clone the repository
git clone https://github.com/opsmill/infrahub-claude-plugin.git

# Install the plugin (run inside Claude Code)
/plugin install ./infrahub-claude-plugin
```

### Option 3: Local Path

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
- Design nodes with attributes and relationships
- Create generics for shared properties and inheritance
- Validate schemas against Infrahub conventions
- Plan schema migrations and updates
- Generate human-friendly IDs and uniqueness constraints

**Example prompts:**
- "Create an Infrahub schema for network devices with hostname and IP address"
- "Design a schema with Sites that contain Racks and Devices"
- "Create an Interface generic with Physical and Logical implementations"
- "How do I extend an existing schema to add new attributes?"
- "What are the best practices for Infrahub schema design?"

**Documentation files:**
| File | Description |
|------|-------------|
| `SKILL.md` | Main skill definition and quick start |
| `reference.md` | Complete schema property reference |
| `validation.md` | Validation commands and migration guide |
| `examples.md` | Ready-to-use schema templates |

## Project Structure

```
.
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── skills/
│   └── schema-creator/
│       ├── SKILL.md             # Skill definition
│       ├── reference.md         # Schema reference
│       ├── validation.md        # Validation guide
│       └── examples.md          # Example schemas
├── CLAUDE.md                    # Project context
├── README.md                    # This file
└── LICENSE                      # MIT License
```

## Resources

- [Infrahub Documentation](https://docs.infrahub.app/)
- [Infrahub Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Schema Library](https://github.com/opsmill/schema-library)
- [OpsMill](https://opsmill.com/)

## License

MIT License - see [LICENSE](LICENSE) for details.
