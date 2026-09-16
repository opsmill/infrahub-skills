---
paths:
  - "skills/*/SKILL.md"
  - "docs/docs/**/*.mdx"
  - "AGENTS.md"
  - ".github/.release-manifest.json"
---

# Registering a Skill

Creating the skill itself: `dev/guides/adding-a-skill.md` §§1-6 and §8

A new skill has to be listed in **five** places. CI
checks none of them, so a skill missing from one ships
invisible to whichever audience reads that surface.

`README.md` is one of those surfaces but not a trigger:
a bare `README.md` glob would match every nested README
in the tree, and the work always starts at the skill's
own `SKILL.md`, which is a trigger.

| Surface | What to add |
| ------- | ----------- |
| `AGENTS.md` | Row in the Quick Reference → Skills table |
| `README.md` | Row in the `## Skills` table **and** an entry in the Project Structure tree |
| `docs/docs/readme.mdx` | Row in the skills table, linking `./skills-reference/<name>.mdx` |
| `docs/docs/skills-reference/<name>.mdx` | New page (drop the `infrahub-` prefix in the filename) |
| `.github/.release-manifest.json` | Name appended to the `skills` array |

The manifest entry is what the published release claims
to ship — a skill absent from it is not in the release.

## When behavior changes

A changed skill already appears in every surface. The
problem is the opposite one: those surfaces now describe
behavior the skill no longer has. Nothing fails, so
nothing flags it.

Stale documentation is worse than none. A reader trusts
it, and search finds it, so a wrong page outranks the
skill it misdescribes.

The usual trigger is the `description` field. It is
copied into three separate tables, so one edit leaves
three stale rows at once.

Check these, in this order:

| Surface | Goes stale when |
| ------- | --------------- |
| `docs/docs/skills-reference/<name>.mdx` | Any behavior change. It describes the skill in prose, so it rots fastest. |
| `AGENTS.md` | The one-line description changed |
| `README.md` | The description changed, or the skill gained or lost files in the Project Structure tree |
| `docs/docs/readme.mdx` | The description changed |
| `dev/guides/`, `dev/knowledges/`, `dev/guidelines/` | A page documents the behavior being changed |

Find them rather than recalling them. Grep the old
claim, and the skill name, across every surface at once:

```bash
grep -rn "<old claim or skill name>" \
  README.md AGENTS.md docs/ dev/ .claude/
```

"Nothing to change" is a complete answer. The point is
that somebody looked.

## Release notes

Towncrier assembles `CHANGELOG.md` from the news
fragments in `changelog/`, and that assembled section
becomes the GitHub Release body — so a new skill ships a
fragment rather than a hand-edited changelog.

Each release also gets a curated page under
`docs/docs/release-notes/`. The new page takes
`sidebar_position: 1` and **every older page shifts down
by one**. Write it before the release pull request
merges, since merging is what tags and publishes.
