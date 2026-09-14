---
paths:
  - ".claude-plugin/plugin.json"
  - ".github/.release-manifest.json"
  - "pyproject.toml"
  - "skills/*/SKILL.md"
  - "uv.lock"
  - "scripts/sync-versions.sh"
---

# Versioning

All skills share one version. A bump touches **five**
files:

1. `.claude-plugin/plugin.json`
2. `.github/.release-manifest.json`
3. `pyproject.toml`
4. Every `skills/*/SKILL.md` frontmatter
   (`metadata.version`)
5. `uv.lock` — any `uv run` rewrites it, so a stale
   version reappears as a stray diff in a later PR

`scripts/sync-versions.sh <version>` does 2-4.
`auto-bump.yml` does 1 before calling it — so a manual
bump has to set `plugin.json` itself:

```bash
VERSION=1.2.9   # the version you are bumping to
jq --arg v "$VERSION" '.version = $v' \
  .claude-plugin/plugin.json > /tmp/p.json \
  && mv /tmp/p.json .claude-plugin/plugin.json
scripts/sync-versions.sh "$VERSION"
```

Set `VERSION` first. With it unset, `jq` writes an empty
`version` and `sync-versions.sh` then exits on its own
`${1:?}` guard, leaving `plugin.json` blanked and nothing
else bumped.

`release.yml` validates 1-4 against the tag and fails
the publish on a mismatch. **Nothing validates 5** —
check `uv.lock` by hand:

```bash
grep -A1 'name = "infrahub-skills"' uv.lock
```
