# Grounding the Draft

Every guess in the step 6 draft, and every recommended
answer, rests on something the user can check. Read the
local rules first; only what they do not settle goes to
the Infrahub documentation.

## The best-practice rules of the other skills

The rules grow over time, so list them each time rather
than relying on the links in the question bank, which
are starting points, not the full set.

- List the file names in `../../infrahub-managing-schemas/rules/`
  and the `yagni-*` files in `../../infrahub-auditing-repo/rules/`.
- Read only the rules that govern a decision in front of
  you.
- Name the rule in the question's basis by its plain
  name (uniqueness-constraints, not a link).
- When the design needs a generator, a check or a
  transform, do the same with that skill's rules
  (`../../infrahub-managing-generators/`,
  `../../infrahub-managing-checks/`,
  `../../infrahub-managing-transforms/`), and ask what it
  needs: what drives it, what it produces, when it runs.

## What the rules do not settle

Look it up in the current Infrahub documentation, such
as what starts a mechanism or how an Infrahub feature
behaves, as
[../../infrahub-common/rules/workflow-information-priority.md](../../infrahub-common/rules/workflow-information-priority.md)
describes:

1. Ask `https://docs.infrahub.app/llms.txt` which pages
   cover the decision, then read them. The documentation
   changes between releases, so find the pages each time
   rather than using one you remember.
2. Name the page by its URL in the question's basis and
   in the brief: on the decision's row, or in its open
   item when the decision stays open.
3. When a page and a local rule disagree, name both and
   ask which applies to the user's Infrahub version, or
   make it an open item when the user cannot reply.
