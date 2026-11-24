# Infrahub skills for Claude Code

Skills for building and running an
[Infrahub](https://github.com/opsmill/infrahub) repository with
Claude Code. They cover schemas, object data files, checks,
generators, transforms, menus, data imports, repository audits,
upgrade planning, and diagnostics.

This branch holds only the files the plugin ships. The source,
the tests, and the documentation are on the `main` branch of
[opsmill/infrahub-skills](https://github.com/opsmill/infrahub-skills).

## What you need

- An Infrahub server, version 1.7 or later. See the
  [Infrahub documentation](https://docs.infrahub.app/).
- `infrahubctl`, to load schemas and objects and to run
  generators. See the
  [infrahubctl documentation](https://docs.infrahub.app/python-sdk/infrahubctl).
- The [Infrahub MCP server](https://docs.infrahub.app/integrations/mcp),
  only for the `infrahub-analyzing-data` skill.

## Skills

The [skills table](https://github.com/opsmill/infrahub-skills#skills)
on `main` lists each skill and what it does. Call a skill by
name, for example `/infrahub:managing-schemas`, or describe the
task and Claude Code loads the skill whose description matches it.

## Load the right skill before editing a file

A request that names a file rather than a task, such as "fix the
failing test in `generators/create_dc.py`", may not load the
matching skill. The
[installation guide](https://github.com/opsmill/infrahub-skills/blob/main/docs/docs/installation-setup.mdx#claude-code-plugin)
gives a `CLAUDE.md` section that maps repository paths to the
skill to read first.

## Report a problem

Open an issue on
[opsmill/infrahub-skills](https://github.com/opsmill/infrahub-skills/issues),
or ask Claude Code to use the `infrahub-reporting-skill-gaps`
skill.

## License

Apache License 2.0. See the `LICENSE` file on this branch.
