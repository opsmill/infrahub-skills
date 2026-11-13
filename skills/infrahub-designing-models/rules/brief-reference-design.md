---
title: brief-reference-design
impact: MEDIUM
tags: brief, reference-design, reuse, grounding
---

# Rule: brief-reference-design

## The rule

The brief has a `## Reference design` section, right
after `## Service`, that names the closest OpsMill
reference design, what the design reuses from it and
where it differs, and the Marketplace schemas it builds
on. The `Closest:`, `Reused:`, `Different:` and
`Marketplace:` lines, and what each may hold, are
defined in
[../references/brief-format.md](../references/brief-format.md).
Choose the design from
[../references/reference-designs.md](../references/reference-designs.md),
and read the Marketplace catalog whole, matching it per
node kind (SKILL.md step 5).

## Why it matters

A design that starts from a worked example inherits
decisions OpsMill has already made and tested: which
object is the service, which kinds are generics, where
pools replace hand allocation. A design that starts
from a blank page reinvents them, and that is where the
wrong node kinds come from. Naming the example also
lets a reviewer compare the two and ask why they differ.

## How to apply

- Read the candidates in step 1, then choose after the
  business and service answers and the user's inputs
  (SKILL.md step 5), before drafting, so the draft's
  guesses can follow it. Recommend it like any other
  answer, with the design as the basis.
- Choose by use case, not by matching words.
- Never copy schema YAML out of a reference design;
  reusable schemas come from the Marketplace.
- A wrong reference design is worse than none. Write
  `Closest: none` with the reason when no design fits.

## Correct

```markdown
## Reference design

Closest: none, no listed design models campus wireless
Marketplace: not searched: the session had no network (O3)
```

## Incorrect

A design named without what it contributes, and a name
that is neither listed nor a full URL.

```markdown
## Reference design

Closest: infrahub-demo-campus
Reused: -
```

## Common mistakes

| Mistake | Why it is wrong |
| ------- | --------------- |
| Naming a design because its node kind names match | The use case decides fit, not the words |
| Copying the reference design's schema files | Reusable schemas come from the Marketplace |
| `Closest: none` with no reason | A reviewer cannot tell whether anyone looked |
