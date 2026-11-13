---
name: harvesting-release-notes
description: >-
  Reads the release notes of Infrahub, infrahub-sdk, or the Infrahub MCP server
  for one release or a range, checks each breaking change and deprecation
  against this repository's shipped skills and against source at the release
  tag, and writes a ranked report of version-gated changes. Reports only.
  Follow the workflow in the body; the description does not summarize it.
  TRIGGER when: a new Infrahub, SDK, or MCP server release is out and the
  skills may still teach what it changed; someone asks which skills a release
  or a range of releases affects; a skill is suspected of teaching removed,
  renamed, or deprecated behavior. DO NOT TRIGGER when: planning a customer's
  Infrahub upgrade, use infrahub-planning-upgrades; one known defect is already
  identified, use analyzing-skill-bugs; turning PR review comments into rules,
  use harvesting-skill-review.
argument-hint: <release or range, e.g. 1.12.0, 1.11.0..1.12.1, sdk 1.23.0..1.24.0, mcp 1.2.0..1.3.0> [notes directory] [source directory]
compatibility: >-
  Requires this repository checked out. `gh` reads the release notes unless
  the user names a local notes directory. Source verification needs a local
  opsmill/infrahub checkout or a named per-release source directory; without
  either, findings are UNVERIFIED.
user-invocable: true
metadata:
  internal: true
  version: 0.1.0
  author: OpsMill
---

# Harvest release notes into skill changes

## Overview

A release changes how Infrahub, the SDK, or the MCP
server behaves, and the skills in `skills/` go on
teaching the old behavior until someone notices. This
skill reads the releases in a range, finds every skill
passage a change touches, confirms the change in source
at the release tag, and writes a report: one ranked
finding per change, listing every passage it affects,
each with the version-gated text to put in the skill.

Write the report to `.release-harvest-<range>.md` at the
repository root, which `.gitignore` covers, unless the
user names another path. A report is a working file, not
a repository artifact.

**It reports; it does not edit skills.** Even when the
user asks to "update the skills", write the report and
offer to file each finding as an issue (step 8). The fix
then starts from that issue in the repository's
test-first pipeline. An edit made here skips the failing
test that proves the change was needed.

## Input

The release or range names its repository by its form:

- `1.12.1`, `1.11.0..1.12.1`, or
  `infrahub-v1.11.0..infrahub-v1.12.1`: `opsmill/infrahub`.
- `sdk 1.23.0..1.24.0`: `opsmill/infrahub-sdk-python`.
- `mcp 1.2.0..1.3.0`: `opsmill/infrahub-mcp-server`.

One request can hold several of these. A range includes
both ends. Pre-releases (`1.12.0b1`) are left out unless
the user asks for them or names one as an end of the range.

The release notes come from `gh` unless the user names a
directory holding them as `<tag>.md`. Source comes from
the local `opsmill/infrahub` checkout, or from a directory
the user names that holds one subdirectory per tag.

## Workflow

### 1. List the releases

```bash
python .agents/skills/harvesting-release-notes/scripts/list_releases.py "<release or range>"
```

Add `--notes-dir <directory>` when the notes are local,
and `--include-prereleases` only when the user asked. The
script sorts by version, not by publish date: a patch to
an older minor is often published after the next minor's
pre-release.

### 2. Read the breaking sections of each release

```bash
gh release view <tag> -R <owner/repo> --json body -q .body
```

Each repository names its sections differently:

- `opsmill/infrahub`: "Breaking changes and required
  actions" and "Deprecations".
- `opsmill/infrahub-sdk-python`: "Removed", "Deprecated",
  and "Changed".
- `opsmill/infrahub-mcp-server`: "Upgrade notes".

Read the release highlights too. A new capability can make
a skill's guidance outdated without breaking it.

**Infrahub release notes also report SDK changes.** Each
Infrahub tag pins an `infrahub-sdk` commit as the
`python_sdk` submodule, and a note about `infrahubctl`,
the SDK, protocols, or Generator tracking usually lives in
that SDK code. Find the commit pinned by the release and
by the one before it:

```bash
git -C <infrahub checkout> ls-tree <tag> python_sdk
git -C <infrahub-sdk-python checkout> describe --tags <commit>
```

Read and cite the SDK at those commits, and name the SDK
release in the finding: `Repository:
opsmill/infrahub-sdk-python` and `Removed in: v1.24.0
(shipped with infrahub-v1.12.0)`.

### 3. Find the skill passages each change touches

Search `skills/` twice for each change:

- **For the name it concerns:** the command, flag,
  field, filter, tool, or setting. Use word boundaries
  (`grep -rnw`, or `\b` in a pattern): a short name such
  as `sso` or `agnostic` otherwise matches "also" and
  "diagnostic".
- **For what the skill claims happens:** the old
  behavior in plain words. A passage can be wrong without
  naming anything from the notes. "The generator produces
  nothing" and "auto-detected from git" were both wrong
  after 1.12, and neither contains a name the notes use.

Record each hit as `path:line`. Passages that need the
same fix belong to one finding. A change that touches no
passage is not a finding: list it in one line under "Not
reported" so the reader knows it was read.

### 4. Confirm each change in source at the tag

Follow
[`../skill-pipeline-common/ground-truth.md`](../skill-pipeline-common/ground-truth.md)
for the reads. With a named source directory, read
`<directory>/<tag>/<path>` instead of the local checkout.
Read the release where the behavior changed and the one
before it, so you see both sides of the change.

**Release notes also document behavior that did not
change.** When the code is the same in the previous
release, the skill was already wrong and the note only
exposed it. That is a correction, not a version change:
write `Removed in: none, not version-bound`, cite the
previous release as evidence, and start `Gate:` with "No
version gate; this applies to every release." followed by
the corrected text.

Pin the evidence: `Verified in: <tag or commit>:<path>`.
A path with no tag or commit does not say which version
you read. When the source does not confirm the change,
write `Verified in: UNVERIFIED` and `Gate: none`, and make
no recommendation. When the source shows the skill is
still correct, drop the finding.

### 5. Rate each finding

Rate by what happens to a user who follows the skill on a
released version. The release notes carry no severity.

- **Critical:** following the skill deletes or corrupts
  data.
- **High:** following the skill fails with an error,
  because something was removed or renamed, or it gives a
  wrong result without losing data.
- **Medium:** the guidance still works, but it is
  deprecated with a stated removal release, or a release
  added a better way or a new warning the skill does not
  mention.

### 6. Write the gate before recommending a change

Before writing any recommendation:

1. Find the deprecation release and the removal release
   in the notes. The removal release is the first release
   where the skill's current guidance is wrong.
   Deprecation alone does not make guidance wrong.
2. Check whether the passage already carries a correct
   gate. If it does, there is no finding.
3. Write the gate in the form
   [`dev/guidelines/skill-authoring.md` § "Release-gate what you teach"](../../../dev/guidelines/skill-authoring.md#release-gate-what-you-teach)
   gives. Name both boundaries, and leave no release
   without working guidance: the old guidance covers at
   least every release before the new behavior became
   available, and the new guidance starts there. Never recommend
   replacing it: users on earlier releases still read the
   skill.
4. When there was no deprecation period, both boundaries
   are the same release. Name it once and write
   `Deprecated in: none`.

### 7. Write the report

Order findings Critical, then High, then Medium. Use this
shape for each, with every field. `Affected` lists every
passage the change touches, separated by commas. A field
ends at the first blank line, so put any explanation in a
paragraph after the list:

```markdown
### Finding 1

- Repository: opsmill/infrahub
- Severity: High
- Affected: skills/<skill>/rules/<file>.md:<line>
- Deprecated in: infrahub-v1.6.0
- Removed in: infrahub-v1.7.0
- Verified in: infrahub-v1.7.0:backend/infrahub/<path>
- Gate: Infrahub 1.6 and later: use <new>. It is required from 1.7. Before 1.7: <old> still works.
```

After the findings, list the releases read, the
pre-releases skipped, and the changes not reported.

### 8. File each verified finding as an issue

Offer to file each verified finding as an issue in
`opsmill/infrahub-skills` with `infrahub-reporting-skill-gaps`.
Pass the finding as its evidence: the affected passages
are its coverage read, and the pinned source is evidence
no session can give. That skill checks the tracker for an
existing report, drafts and redacts the issue, and hands
it to `infrahub-reporting-issues`, which shows the draft
to the user and files nothing without approval.

One finding is one issue. Do not file an UNVERIFIED
finding: leave it in the report for a person to check.

Once an issue exists, `analyzing-skill-bugs <issue number>`
starts the fix from it.

## Common mistakes

- **Recommending a replacement.** "Use `name__contains`"
  alone leaves users on the earlier release with guidance
  that does not work for them.
- **Gating on the deprecation release.** Guidance is not
  wrong until the removal release, so a gate that names
  only the deprecation release points users at the wrong
  boundary.
- **Citing a pre-release.** A beta tag is not a release
  users install. Cite the final release.
- **A path with no version.** `backend/infrahub/x.py` does
  not say which release you read. Pin a tag or a commit.
- **Ranking a quiet deletion below a loud error.** A
  change that deletes data without an error is Critical,
  above a renamed flag that fails at once.
- **Editing the skill.** This skill writes the report.
  The change goes through an issue, then the test-first
  pipeline.
- **Gating an old defect.** When the previous release
  behaves the same way, a version gate tells users on that
  release the old guidance was right. It was not.
- **Citing Infrahub for an SDK change.** The code is in
  the SDK commit the Infrahub tag pins; cite that.

## Boundaries

Follow the repository-wide boundaries in
[`../../../AGENTS.md`](../../../AGENTS.md) § Boundaries.
