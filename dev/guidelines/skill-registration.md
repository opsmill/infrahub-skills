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

## Release notes

PR labels drive the auto-generated draft, but each
release also gets a curated page under
`docs/docs/release-notes/`. The new page takes
`sidebar_position: 1` and **every older page shifts down
by one**. Merging to `main` regenerates the GitHub draft
body, so paste the curated notes into the draft after
the last PR lands and before publishing.
