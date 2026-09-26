---
title: sources-enumerate-every-hop
impact: CRITICAL
tags: release-notes, breaking-changes, gh, patch-releases
---

# Rule: sources-enumerate-every-hop

## The rule

Read the notes of **every** Infrahub release between the
current version and the target, patches included, and
attribute each finding to the one release that
introduced it.

## Why it matters

A plan built from the target release's notes alone
misses what the releases in between broke, and the
upgrade then fails partway through on a change the plan
never named.

Patch releases carry breaking changes too. 1.11.3, a
patch, changed the shape of the `422` errors that
`POST /api/schema/load` and `POST /api/schema/check`
return, so a CI job that parses those errors breaks. A
plan that reads only the `X.Y.0` releases passes
straight through it.

## How to apply

1. List the releases, keeping only the `infrahub-v`
   tags. The same repository also tags the Python SDK
   (`python-sdk-v*`), which is not an upgrade target.
   `gh` returns them newest first by date, so sort by
   version before walking the range:

   ```bash
   gh release list --repo opsmill/infrahub --limit 400 \
     --exclude-pre-releases --json tagName \
     --jq '.[].tagName | select(startswith("infrahub-v"))'
   ```

2. Read each release in the range, from the one after
   the current version up to and including the target:

   ```bash
   gh release view infrahub-v1.11.3 --repo opsmill/infrahub --json body --jq .body
   ```

3. **Read the prose; do not parse for a flag.** No
   field marks a release as breaking, and the heading
   varies from release to release: `## Breaking
   changes`, `### Breaking Changes` with a link anchor,
   `### Breaking changes` under `## Before upgrading`,
   an inline `BREAKING CHANGE` marker, or a line in the
   `### Changed` list. Read the upgrade-related parts of
   every body. Bodies are long, so skip the feature
   write-ups once the breaking, deprecation, and
   before-upgrading content is read.
4. Stamp each row's `Release` with the single version
   that introduced the change, and name the change
   itself. A release with nothing breaking needs no
   row.
5. Put the `Source` link to that release's notes, or
   to a deprecation guide the notes link to.

## Examples

Compliant: each change named, each row one release.

```markdown
| Change | Release | ... |
| --- | --- | --- |
| `IPAddressGetNextAvailable` deprecated for `InfrahubIPAddressGetNextAvailable` | 1.4.0 | ... |
| Schema load and check return one `422` entry per offending field | 1.11.3 | ... |
```

Non-compliant: a range standing in for changes nobody
read.

```markdown
| Change | Release | ... |
| --- | --- | --- |
| Review intermediate release notes | 1.4.0–1.11.3 | ... |
```

## Common mistakes

- Reading only the target, because the user asked
  what is new in it.
- Reading only minor releases (`X.Y.0`) and skipping
  the patches.
- Treating a release with no `Breaking changes` heading
  as safe.
- Letting `python-sdk-v*` tags into the range.
