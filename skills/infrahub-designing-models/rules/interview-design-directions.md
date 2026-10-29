---
title: interview-design-directions
impact: HIGH
tags: interview, directions, reuse, marketplace, reference-design
---

# Rule: interview-design-directions

## The rule

After the scope check, the reference design and the
Marketplace search (SKILL.md step 5), and before the
draft sketch, ask one question block that offers two or
three design directions:

1. The question line uses the layer `direction`:
   `**Q<n> (direction):** <question>?`.
2. Each option, `- A. <name>`, is one direction. Exactly
   one is marked `**(Recommended)**`.
3. Under each option, list its decisions as indented
   items with an ID made of the option's letter and a
   number: `- A1. <topic>: <choice>`.
4. The first decision of every direction is `Reuse`:
   a reference design from
   [../references/reference-designs.md](../references/reference-designs.md),
   a Marketplace schema found in step 5
   (`infrahub/base-schemas`), or `none` for a custom
   model.
5. Every direction lists the same topics. Apart from
   `Reuse`, list only topics where at least two
   directions choose differently, such as what the
   service node is, where a value comes from (a pool,
   the requester, another system), or how the scope is
   split. No two directions make the same choice on
   every topic.
6. The lead-in says, without a question mark, that the
   user can pick one direction or combine them by ID
   ("A with B2").

The block follows
[interview-one-question-recommended.md](interview-one-question-recommended.md)
in everything else. Draft the step 6 sketch from the
direction the user picks, with the decisions they
borrow from another.

In the brief, the direction is one row of the decision
log, in the format in
[../references/brief-format.md](../references/brief-format.md).
Tag it `recommended` when the user took the
recommended direction as it was, and `stated` when they
picked another one or combined them. When the user
cannot reply, build on the recommended direction and tag
the row `open`, with an open item asking which direction
to follow that names the others.

## Why it matters

People choose between concrete alternatives faster than
they answer questions about a model they cannot see, and
the choice they would make is often a mix ("the demo's
service model, but our own site kinds"). A direction
that differs from another only in its name gives the
user nothing to choose. Decisions without IDs cannot be
combined, and a direction that does not say what it
reuses hides the main trade-off: a published schema or a
worked example saves work, a custom model fits the
request exactly but has to be maintained.

## How to apply

- Build the directions from what step 5 found: the
  closest reference design, each Marketplace schema that
  covers a node kind the design needs, and a custom
  model. When the Marketplace was not searched, the
  directions use the reference design or `none`.
- Recommend the direction that fits the business and
  service answers best, and say why in the Basis.
- Keep each direction to the two to five decisions that
  separate it from the others. The draft sketch carries
  the rest.
- Log each decision of the chosen direction as its own
  decision row as well: `recommended` when it came with
  the recommended direction, `stated` when the user
  borrowed it from another.

## Correct

```markdown
Two directions fit what you described. Pick one, or combine them by ID, such as A with B2.

**Q6 (direction):** Which direction should the model follow?

- A. Follow infrahub-demo-sp  **(Recommended)**
  - A1. Reuse: infrahub-demo-sp
  - A2. Route distinguishers: allocated from a pool
  - A3. VPN sites: one L3VpnSite per customer site
- B. A custom model
  - B1. Reuse: none
  - B2. Route distinguishers: entered by the requester
  - B3. VPN sites: a list of sites on the VPN

**Basis:** you sell L3VPN over an MPLS backbone, which is what infrahub-demo-sp models (strong)
```

## Incorrect

Three directions that differ only in their names, with
no IDs to combine and no word on what each reuses.

```markdown
**Q6 (direction):** Which direction should the model follow?

- A. Lean model  **(Recommended)**
- B. Standard model
- C. Full model

**Basis:** a lean model is easier to start with (weak basis)
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Three full sketches side by side | The user reads three near-identical tables to find two differences |
| Decisions written as prose under each option | The user cannot combine them by ID |
| A topic every direction answers the same way | It is not a choice; it belongs in the draft |
| No `Reuse` decision | The trade-off between reuse and a custom model is hidden |
| Directions offered before the business and service answers | They rest on guesses, so the choice is not real |
