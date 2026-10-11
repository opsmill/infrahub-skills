---
title: brief-reference-design
impact: MEDIUM
tags: brief, reference-design, reuse, grounding
---

# Rule: brief-reference-design

## The rule

The brief has a `## Reference design` section, right
after `## Service`, that names the closest OpsMill
reference design and what the design follows from it:

```markdown
## Reference design

Closest: infrahub-demo-sp
Reused: the service-with-sites pattern (L3Vpn and L3VpnSite)
Different: route distinguishers come from a pool, not from the order
```

- `Closest:` names a design from
  [../references/reference-designs.md](../references/reference-designs.md),
  or the full `https://github.com/opsmill/...` URL of a
  newer `infrahub-demo-*` or `infrahub-solution-*`
  repository you found and read, or `none` followed by
  the reason no design fits.
- `Reused:` says which pattern, node kinds or service
  objects the design follows. It is required whenever a
  design is named.
- `Different:` says where this design departs from it.

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
