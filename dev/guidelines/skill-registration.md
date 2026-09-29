---
paths:
  - "skills/*/SKILL.md"
  - "docs/docs/**/*.mdx"
  - "AGENTS.md"
  - ".github/.release-manifest.json"
---

# Registering a Skill

Creating the skill itself: `dev/guides/adding-a-skill.md` §§1-6 and §8

A new skill has to appear on every surface below. A
skill missing from one ships invisible to whichever
audience reads that surface, and readers pick a skill
from the router and the front page, not from its
`description`. A skill with `user-invocable: false` in
its frontmatter, like `infrahub-common`, is exempt: it
goes on none of these surfaces and is left out of the
router's count.

`README.md` is one of those surfaces but not a trigger:
a bare `README.md` glob would match every nested README
in the tree, and the work always starts at the skill's
own `SKILL.md`, which is a trigger.

| Surface | What to add | Checked by |
| ------- | ----------- | ---------- |
| `AGENTS.md` | Row in the Quick Reference → Skills table | `check-skill-registration.py` |
| `README.md` | Row in the `## Skills` table **and** an entry in the Project Structure tree | `check-skill-registration.py` |
| `docs/docs/readme.mdx` | Row in the skills table, linking `./skills-reference/<name>.mdx`. Check the "When you would reach for it" scenarios still cover it | `check-skill-registration.py` (the row only) |
| `docs/docs/choosing-a-skill.mdx` | Row in the matching lifecycle group, the skill count in the opening sentence, and a pair table under "Pairs that are easy to confuse" when readers could mistake it for another skill | `check-skill-registration.py` |
| `docs/docs/skills-reference/<name>.mdx` | New page (drop the `infrahub-` prefix in the filename), in the shape below | `check-docs-skill-names.py` (exists), `check-skill-registration.py` (shape) |
| `docs/sidebars.ts` | Entry for the new page | `check-docs-sidebar.py` |
| `.github/.release-manifest.json` | Name appended to the `skills` array | `check-skill-registration.py` |

All three scripts run in `uv run invoke lint` and in CI.
They check that an entry exists, not that its prose is
right, so the scenarios and pair tables stay a judgement.
`uv run invoke lint` also skips `npm run build` in
`docs/`, which is what catches a broken link: run it
before you push.

## Reference page shape

Every `skills-reference/*.mdx` page opens with a
``Skill: `infrahub-<name>` `` line and carries these
`##` sections, in this order:

1. When to use
2. What it produces
3. Example prompts
4. Key rules enforced
5. Common mistakes it catches

Add the skill's own sections after them (Running it,
Loading it, and so on). End with "Not sure this is the
right skill?" exactly when the router has a pair table
naming the skill, and point it at that table.

Write it the way the other pages do: second person,
what the reader gets rather than how the skill works
inside, and links to the Infrahub guides it depends on
rather than copies of them.

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
| `docs/docs/choosing-a-skill.mdx` | What the skill starts from or produces changed (its row), or a new skill is easy to confuse with it (a pair table, plus "Not sure this is the right skill?" on both pages) |
| `dev/guides/`, `dev/knowledges/`, `dev/guidelines/` | A page documents the behavior being changed |

Find them rather than recalling them. Grep the old
claim, and the skill name, across every surface at once:

```bash
grep -rn "<old claim or skill name>" \
  README.md AGENTS.md docs/ dev/ .agents/skills/
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
