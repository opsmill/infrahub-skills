---
name: infrahub-reporting-issues
description: >-
  Reports bugs and feature requests against the right Infrahub-ecosystem GitHub repository.
  Classifies the request, routes it (with the main `opsmill/infrahub` repo as the safe fallback when in doubt),
  searches for existing duplicates, gathers conservative environment info for bugs, and prepares the issue
  for the user to review before any submission.
  TRIGGER when: user wants to report a bug, file an issue, request a feature, open a ticket, or escalate a problem
  in any opsmill/infrahub-* project (SDK, Ansible, VS Code, MCP, Helm, schema-library, sync, backup, nornir, skills).
  DO NOT TRIGGER when: the user wants to fix the bug themselves locally, write a test, or debug code without filing.
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
  - WebFetch
metadata:
  version: 1.2.5
  author: OpsMill
---

# Infrahub Issue Reporter

## Overview

Help the user file a bug report or feature request
against the correct Infrahub-ecosystem repository on
GitHub. The skill does **not** auto-submit — it
prepares a complete, sanitized issue and stops at the
user's review gate. Submission only happens after the
user explicitly approves both the content and the
submission method.

The ecosystem has 11 candidate repos. Most users will
not know which one owns their problem. The skill's
job is to make a confident guess from local-repo
context, confirm it with the user, search for
duplicates, and produce a draft that matches the
target repo's intake form.

## When to Use

Trigger this skill when the user says things like:

- "I think I found a bug in Infrahub"
- "How do I report this issue?"
- "I'd like to request a feature"
- "Where should I file this?"
- "This isn't working — I want to open a ticket"

Do not trigger if the user is debugging locally and
hasn't expressed an intent to file an issue. Filing
is the action that distinguishes this skill from
general troubleshooting.

## Workflow

Follow these steps in order. Stop at every user-gate
step — never proceed past one without explicit
confirmation.

### 1. Capture the problem

Ask the user to describe the problem in their own
words if they haven't already. Don't probe yet —
just listen. Take note of any product names, version
numbers, error messages, or workflow context they
mention; they feed every later step.

### 2. Classify

Decide whether this is a **bug**, **feature
request**, or **question/usage help**. Use 1-2
follow-ups only if classification is ambiguous:

- "Did this work before and now doesn't, or is it
  something that's never existed?"
- "Do you have a reproduction case, or is this an
  intermittent observation?"
- "Is the desired behavior documented anywhere, or
  is this new functionality you're asking for?"

If the user describes a workaround they're already
using, lean toward "feature request" (the bug has a
workaround → real problem is the missing
ergonomics). If the user describes a crash, wrong
output, or 500-level error, lean toward "bug". If
the user is asking how to do something, route them
to Discord/discussions instead of filing an issue
— don't open issues for support questions.

### 3. Route to a repo

Read `reference.md` for the full 11-repo registry,
detection cues, and template availability. Apply this
detection logic in order:

1. Read the local working directory for filesystem
   cues (`infrahub.toml`, `pyproject.toml` deps,
   `galaxy.yml`, `.claude-plugin/plugin.json`, etc.)
2. Cross-reference detected cues with what the user
   said. A user complaining about Ansible playbooks
   in a repo with no Ansible cues is still an
   Ansible issue.
3. Pick the most specific match.

**The default-to-main rule**: if detection is
ambiguous, if multiple repos match equally, if the
user expresses any uncertainty about which component
is at fault, or if the symptom plausibly lives at
the platform layer — **default to `opsmill/infrahub`**.
The main repo can re-route an incoming issue to a
sub-repo more easily than a sub-repo can re-route
back. Erring toward main is cheaper than erring
toward a wrong specialized repo.

Present your guess to the user with a one-sentence
rationale and ask them to confirm or correct. Example:

> "Based on `infrahub-sdk` in your `pyproject.toml`
> and the error mentioning `InfrahubClient`, this
> looks like an `opsmill/infrahub-sdk-python` issue.
> Confirm?"

### 4. Search for duplicates

Always search both bugs and features. Use the first
available method:

1. **`gh` CLI** — `gh search issues --repo <owner/repo>
   --state all "<keywords>"`. Pull keywords from the
   user's description plus any error message strings.
   Run a second pass with synonyms if the first
   returns nothing.
2. **MCP GitHub server** — if `gh` is not installed,
   use whichever GitHub MCP tool is available in the
   user's environment.
3. **Manual** — if neither is available, give the
   user the GitHub search URL and ask them to check.

Show the user the top 3-5 matches with title, state
(open/closed), and a one-line excerpt. Ask:

> "Is your issue covered by any of these? If yes,
> we'll add a comment instead of opening a new one."

If a match exists, switch to **comment mode**:
prepare a comment that adds the user's new
information (their version, reproduction, etc.) to
the existing issue. Otherwise, proceed.

### 5. Gather environment info (bugs only)

For features, skip this step. For bugs, collect
**only**:

- The relevant product version(s) — e.g., Infrahub
  server version, SDK version, Ansible collection
  version, plugin version.
- Operating system + architecture (e.g., `macOS 14
  arm64`, `Ubuntu 22.04 x86_64`).
- Python or runtime version if relevant to the
  component.

That's it. **Do not** collect file paths, project
structure, logs verbatim, env dumps, `docker
compose ps` output, or anything that could leak
internal state. The
[environment-info-sanitization rule](rules/environment-info-sanitization.md)
governs what is and is not allowed in the issue body
— read it before composing the bug section.

Where to find versions:

| Component | Command |
| --------- | ------- |
| Infrahub server | `infrahubctl --version`, or check `image:` tag in compose file |
| Python SDK | `pip show infrahub-sdk` |
| Ansible collection | `ansible-galaxy collection list opsmill.infrahub` |
| Nornir plugin | `pip show nornir-infrahub` |
| Helm chart | `helm list -n <namespace>` |
| infrahub-sync | `infrahub-sync --version` |
| infrahub-backup | `infrahub-backup --version` |
| MCP server | check MCP client config or `pip show infrahub-mcp` |
| VS Code extension | Extensions panel in VS Code |
| Skills plugin | `.claude-plugin/plugin.json` version field |

If a version can't be determined cleanly, mark it
`unknown` rather than guessing or running broader
discovery commands.

### 6. Render the issue

If the target repo has a `.github/ISSUE_TEMPLATE/`
directory, fetch the matching template (`bug_report.yml`
for bugs, `feature_request.yml` for features) and
follow its form fields. Use:

```bash
gh api repos/<owner>/<repo>/contents/.github/ISSUE_TEMPLATE/bug_report.yml --jq '.content' | base64 -d
```

Repos that ship issue templates:

- `opsmill/infrahub`
- `opsmill/infrahub-sdk-python`
- `opsmill/infrahub-ansible`
- `opsmill/nornir-infrahub`

Repos without templates fall back to
`templates/bug.md` or `templates/feature.md` in this
skill.

**Title conventions**: use the form
`<area>: <imperative summary>`, keep it under 72
characters, no trailing punctuation. Examples:

- `SDK: InfrahubClient.create() raises on empty list payload`
- `Schema: hierarchical generic loses parent on rename`
- `Docs: clarify human_friendly_id behavior for inherited nodes`

### 7. User review gate (mandatory)

Present the rendered issue to the user. Show:

- Target repo and URL
- Final title
- Full body (markdown)
- Whether this is a new issue or a comment on an
  existing one

Ask: "Does the content look right? Anything to add
or remove before we proceed?"

**Do not skip this step.** Iterate with the user
until they explicitly approve the content.

### 8. Pick a submission method

Once content is approved, ask the user how they want
to submit:

1. **`gh issue create`** — direct via the CLI. Use
   `gh issue create --repo <owner/repo> --title
   "..." --body "..."`. Show the resulting URL.
2. **MCP GitHub server** — if the user has a GitHub
   MCP server, use it. Confirm the tool name with
   the user before invoking.
3. **Manual** — print the title and body as
   copy-paste-ready markdown, plus the "New issue"
   URL for the target repo:
   `https://github.com/<owner>/<repo>/issues/new`.

Never assume a default — always ask. After the user
picks a method, execute it.

### 9. Confirm

After submission, give the user:

- The new issue URL (for gh/MCP submissions)
- A one-line summary of what was filed
- A reminder that they can subscribe to the issue
  for updates

## Rule Categories

| Prefix | Category | Description |
| ------ | -------- | ----------- |
| env | Environment info | What can and cannot appear in issue bodies |

See [rules/_sections.md](rules/_sections.md) for the
index.

## Supporting References

- [reference.md](reference.md) — the 11-repo
  registry with detection cues, descriptions, and
  template availability. **Read this in step 3.**
- [templates/bug.md](templates/bug.md) — generic
  fallback bug template for repos without a
  `.github/ISSUE_TEMPLATE/`.
- [templates/feature.md](templates/feature.md) —
  generic fallback feature template.
- [rules/environment-info-sanitization.md](rules/environment-info-sanitization.md)
  — what to redact before submitting. Security-critical;
  read this for every bug report.

## Anti-patterns

- **Submitting without explicit user approval.**
  The user gate in step 7 is not optional. A
  surprise GitHub issue on a public repo is hard to
  unwind.
- **Filing in a sub-repo when the symptom is
  ambiguous.** When in doubt, file in
  `opsmill/infrahub` and let the maintainers
  re-route. Wrong sub-repo issues create more work
  for everyone.
- **Filing a duplicate.** If a search match exists,
  default to adding a comment with new info instead
  of opening a new issue.
- **Pasting full logs or `docker compose` output.**
  These leak hostnames, IPs, container names, and
  sometimes secrets. Stick to versions + OS for v1.
- **Filing support questions as bugs.** "How do I
  do X?" belongs in Discord or GitHub Discussions,
  not Issues.
