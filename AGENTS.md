# AGENTS.md

This file provides guidance to AI coding assistants working with this repository.

## Repository Overview

This is a Claude Code plugin for [Infrahub](https://github.com/opsmill/infrahub), the infrastructure data management platform by OpsMill. The plugin provides skills covering the full Infrahub development lifecycle: schema design, data population, validation checks, generators, transforms, menu customization, and live data analysis.

The repository is a pure Markdown-based skills project (no Python code). Each skill is defined in its own directory under `skills/` with rules, examples, and reference documentation. Skills follow the [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) format.

## Project Structure

@dev/knowledges/architecture.md

## Getting Started

@dev/guides/getting-started.md

## Development Guides

@dev/guides/adding-a-skill.md
@dev/guides/running-evals.md

## Domain Knowledge

@dev/knowledges/skill-writing-guide.md
@dev/knowledges/infrahub-concepts.md

## Custom Commands

@dev/commands/

## Quick Reference

### Skills

| Skill | Directory | Description |
| ------- | ----------- | ------------- |
| `infrahub-managing-schemas` | `skills/infrahub-managing-schemas/` | Schema nodes, generics, attributes, relationships |
| `infrahub-managing-objects` | `skills/infrahub-managing-objects/` | YAML data files for infrastructure objects |
| `infrahub-managing-checks` | `skills/infrahub-managing-checks/` | Python validation checks for proposed changes |
| `infrahub-managing-generators` | `skills/infrahub-managing-generators/` | Design-driven automation |
| `infrahub-managing-transforms` | `skills/infrahub-managing-transforms/` | Data transforms (Python/Jinja2) |
| `infrahub-managing-menus` | `skills/infrahub-managing-menus/` | Custom navigation menus |
| `infrahub-analyzing-data` | `skills/infrahub-analyzing-data/` | Live data analysis via MCP server |
| `infrahub-auditing-repo` | `skills/infrahub-auditing-repo/` | Audit repository against best practices |

### Key Directories

- `skills/` — Skill definitions with rules, examples, and references
- `eval.yaml` — skillgrade eval config (all skills)
- `graders/` — Deterministic grader scripts per skill
- `skills/infrahub-common/` — Shared references and cross-cutting rules
- `hooks/` — Hook definitions for Infrahub project detection
- `scripts/` — Utility scripts (e.g., `sync-versions.sh`)
- `dev/` — Development guides, domain knowledge, and AI commands
- `.claude-plugin/` — Plugin manifest

### Versioning

All skills share a unified version. When bumping, update together:

1. `.claude-plugin/plugin.json`
2. `.github/.release-manifest.json`
3. Every `skills/*/SKILL.md` frontmatter
