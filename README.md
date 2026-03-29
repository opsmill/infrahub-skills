# Infrahub AI Skills

AI skills for developing with [Infrahub](https://github.com/opsmill/infrahub). Install the skills, open your Infrahub project, and start building — your AI coding assistant automatically uses the right skill for each task.

```bash
# Install all Infrahub skills into your project
npx skills add opsmill/infrahub-skills
```

Once installed, open any Infrahub project and start working — try *"describe what this schema does"* to explore, or *"add a status attribute to Device"* to make a change.

---

## What You Can Do With It

- **Build a working schema from a description** — describe your data model in plain terms and the Schema Creator produces valid Infrahub schema YAML with appropriate node types, attribute kinds, and relationships, without requiring manual study of the schema format first.
- **Generate automation logic from a plain description** — describe what you want to automate (for example, "create a BGP session for each spine-leaf pair in my fabric design") and the Generator Creator produces a working `InfrahubGenerator` implementation for that specific case.
- **Get working configuration templates for your data model** — describe the output format you need and the Transform Creator produces a transform and Jinja2 template that reads from your specific schema, rather than a generic placeholder example.
- **Write Infrahub CI pipeline checks without SDK expertise** — describe what a proposed change should or should not allow and the Check Creator produces a working `InfrahubCheck` implementation with the correct GraphQL queries and `.infrahub.yml` registration.
- **Work through design decisions before building** — pair the skills with a spec-driven development (SDD) framework to plan before you build: capture requirements, validate the design against Infrahub conventions, and break the work into discrete tasks before any code is generated.
- **Query and analyze a live Infrahub instance** — the Analyst skill connects to a running instance via MCP and answers operational questions directly: cross-node correlation, drift detection, blast-radius analysis, and data quality audits.
- **Audit an existing Infrahub repo for best practices** — the Repo Auditor checks your repository against Infrahub conventions: schema naming, relationship identifiers, `.infrahub.yml` registration, and structural patterns — then generates a report regarding what to fix and why.

---

## How It Works

The skills give your AI agent domain-specific knowledge about Infrahub: schema design, data modeling, validation checks, generators, transforms, and menu customization. When you make a request inside an Infrahub project, the agent picks the appropriate skill and applies Infrahub conventions automatically — correct naming, relationship patterns, `.infrahub.yml` registration, and so on.

There are two ways to work, depending on the complexity of what you're building.

### Direct Mode — Just Ask

For targeted changes, skip the ceremony. Describe what you want and the agent handles it using the right skill.

**Examples:**

- *"Add a `contract_start_date` attribute to `InfraCircuit`"* — the agent uses **schema-creator**, applies naming conventions, and updates the schema file.
- *"Create a check that validates every device has a primary IP"* — the agent uses **check-creator**, writes the Python class and GraphQL query, and registers it in `.infrahub.yml`.
- *"Add a menu section for IP address management"* — the agent uses **menu-creator** and produces the YAML with correct icon references and hierarchy.

This is the fastest path for well-scoped work: adding attributes, writing a check, populating objects, creating a transform. No planning step needed. It's also how most people start — install the skills, describe what you need, and iterate from there.

### Spec-Driven Development — Plan, Then Build

For anything beyond a simple, self-contained change — designing a new schema node with relationships, building a generator chain, or standing up an entire new domain — you should use a spec-driven development (SDD) framework to plan first, then let the agent execute against the plan.

The SDD workflow forces the agent to reason before it builds. You write a natural-language spec describing what you want, the agent produces a plan validated against Infrahub skills, breaks it into discrete tasks, and then implements each one using the correct skill. This matters because a schema node with incorrect relationship cardinality or a generator missing `allow_upsert` will cost you debugging time later — the planning step catches those issues upfront.

A typical SDD workflow looks like:

1. **Specify** — describe the feature. The agent captures requirements and selects the appropriate workflow (schema, objects, checks, generators, transforms, or menus).
2. **Plan** — the agent creates an implementation plan and validates design artifacts against Infrahub skills.
3. **Tasks** — the plan is broken into discrete tasks, each annotated with which skill to use.
4. **Implement** — the agent executes each task, invoking the correct Infrahub skill for each one.

Any SDD framework that supports spec → plan → task → implement workflows will work. The [infrahub-template](https://github.com/opsmill/infrahub-template) repository includes a pre-configured SDD setup you can use as a starting point.

**When to use which approach:**

| Scenario | Approach |
| -------- | -------- |
| Add an attribute to an existing node | Direct |
| Write a validation check | Direct |
| Create a new menu section | Direct |
| Populate a batch of objects from a spreadsheet | Direct |
| Design a new schema node with relationships | Spec-driven |
| Build a cascading generator chain | Spec-driven |
| Stand up a complete new domain (schema + objects + checks + generators) | Spec-driven |
| Refactor relationships across multiple schema files | Spec-driven |

---

## Who This Is For

**Evaluating Infrahub**
Someone exploring Infrahub who wants to see what their specific use case looks like in practice — not a generic demo, but their actual data model or automation workflow. The skills accept a description of the use case and produce real Infrahub resources from it, so the evaluation is grounded in something that actually runs rather than documentation examples. They can also explain how Infrahub handles a particular requirement and what the tradeoffs are between different approaches.

**Building with Infrahub**
A team actively building out an Infrahub implementation — defining schemas, writing generators, creating configuration transforms. The skills cover each part of the build lifecycle and apply Infrahub's patterns to the specific resources being built. Pairing with an SDD framework is especially useful for multi-part tasks where the correct structure isn't obvious upfront.

**Extending an existing Infrahub implementation**
A team already running Infrahub who needs to continue extending it — adding schema nodes, modifying generators, integrating with external data sources. The skills work with existing implementation context and handle the Infrahub side of integrations, including producing `infrahub-sync` diffconfigs for sources like spreadsheets or external CMDBs.

---

## Skills

| Skill | What it does |
| ----- | ------------ |
| **schema-creator** | Describe your use case and get best-practice schema design — nodes, generics, attributes, relationships, hierarchies, and migrations |
| **object-creator** | Create YAML data files for infrastructure objects with correct references and load order |
| **check-creator** | Write Python validation checks (`InfrahubCheck`) for proposed change pipelines |
| **generator-creator** | Build design-driven generators with idempotent create-or-update patterns |
| **transform-creator** | Create data transforms (Python, Jinja2, or hybrid) for configs, reports, and exports |
| **menu-creator** | Define custom navigation menus for the Infrahub web UI |
| **analyst** | Query and correlate live Infrahub data via the MCP server (requires MCP connection) |
| **repo-auditor** | Audit your repository against Infrahub best practices |

Each skill lives in `skills/<name>/` with a `SKILL.md` entry point, reference docs, examples, and modular rules. Shared references (GraphQL patterns, `.infrahub.yml` format, git integration) are in `skills/common/`.

---

## Prerequisites

- An AI coding assistant that supports skills or custom context files (Claude Code, GitHub Copilot, Cursor, Windsurf, Amp, Cline, Codex, or similar)
- A running Infrahub instance, for loading and testing generated resources ([Infrahub installation docs](https://docs.infrahub.app/))
- `infrahubctl`, for loading schemas, objects, and running generators ([infrahubctl docs](https://docs.infrahub.app/python-sdk/infrahubctl))
- Analyst skill only: an Infrahub MCP server configured and connected to your AI tool ([setup guide](https://docs.infrahub.app/integrations/mcp))

---

## Installation

### npx (Recommended)

The `npx skills` CLI automatically installs skills for whichever AI tools you have configured:

```bash
npx skills add opsmill/infrahub-skills
```

This detects your installed AI tools (Claude Code, GitHub Copilot, Cursor, Amp, Cline, Codex, and others) and installs the skills in the correct format for each one. Use `--yes` to skip the interactive skill selection prompt and install all skills.

### Claude Code Plugin

If you use Claude Code, you can also install as a plugin via the OpsMill marketplace:

```bash
/plugin marketplace add opsmill/claude-marketplace
/plugin install infrahub@opsmill
```

The plugin auto-detects Infrahub projects on session start by looking for `.infrahub.yml`, `infrahub.toml`, or schema files with `version: "1.0"` and `nodes:`/`generics:` keys.

### Manual Copy

Copy the `skills/` directory into your project so the assistant discovers the files directly:

```bash
git clone https://github.com/opsmill/infrahub-skills.git
cp -r infrahub-skills/skills /path/to/your-infrahub-project/
rm -rf infrahub-skills
```

Always include `skills/common/` — it contains shared references that all skills depend on.

### Tool-Specific Setup

After installing skills (via `npx` or manual copy), some tools benefit from additional configuration:

**GitHub Copilot** — create `.github/instructions/infrahub.instructions.md`:

```markdown
---
applyTo: '**/*.py,**/*.yml,**/*.yaml'
---

For Infrahub development guidance, refer to the skill files in skills/.
```

See [GitHub Copilot custom instructions docs](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions).

**Cursor** — create `.cursor/rules/infrahub.mdc`:

```markdown
---
description: Infrahub development guidance
globs: ["**/*.py", "**/*.yml", "**/*.yaml"]
alwaysApply: false
---

For Infrahub development guidance, refer to the skill files in skills/.
```

See [Cursor Rules docs](https://cursor.com/docs/rules).

**Windsurf** — Windsurf picks up Markdown files as context automatically. Optionally reference them from `.windsurfrules`. See [Windsurf Memories & Rules docs](https://docs.windsurf.com/windsurf/cascade/memories).

---

## Project Structure

```text
.
├── .claude-plugin/
│   └── plugin.json              # Plugin manifest
├── hooks/
│   └── hooks.json               # Hook definitions
├── hooks-handlers/
│   └── session-start.sh         # Infrahub project detection
├── skills/
│   ├── common/                  # Shared references and rules
│   ├── schema-creator/          # Schema design
│   ├── object-creator/          # Data population
│   ├── check-creator/           # Validation checks
│   ├── generator-creator/       # Design-driven generators
│   ├── transform-creator/       # Data transforms
│   ├── menu-creator/            # Navigation menus
│   ├── analyst/                 # Live data analysis (MCP)
│   └── repo-auditor/            # Best-practice audits
├── CLAUDE.md
├── README.md
└── LICENSE                      # Apache 2.0
```

---

## Resources

- [Infrahub Documentation](https://docs.infrahub.app/)
- [Infrahub Schema Guide](https://docs.infrahub.app/guides/create-schema)
- [Infrahub Template](https://github.com/opsmill/infrahub-template) — project template for getting started with Infrahub
- [Schema Library](https://github.com/opsmill/schema-library)
- [OpsMill](https://opsmill.com/)

---

## About Infrahub

[Infrahub](https://github.com/opsmill/infrahub) is an open source infrastructure data management and automation platform (Apache 2.0), developed by [OpsMill](https://opsmill.com). It gives infrastructure and network teams a unified, schema-driven source of truth for all infrastructure data — devices, topology, IP space, configuration — with built-in version control, a generator framework for automation, and native integrations with Git, Ansible, Terraform, and CI/CD pipelines.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
