---
title: Surface Assumptions Before Generating Artifacts
impact: HIGH
tags: execution, discipline, ambiguity, clarification, schema, objects, generators
---

## Surface Assumptions Before Generating Artifacts

Impact: HIGH

Infrahub artifacts (schemas, objects, checks, generators,
transforms, menus) are interconnected: a namespace choice
propagates into protocols, relationship identifiers, and
data files; a `kind` becomes part of every peer reference.
Silently picking these values hides decisions the user
would have made differently, and the cost of changing them
later is high (rename cascades, regenerated protocols,
data reloads).

When a request leaves a structural choice ambiguous,
surface the assumption explicitly -- either by asking, or
by stating the choice up front and inviting a redirect --
rather than committing to it silently.

### Choices That Warrant Surfacing

| Ambiguity | Why it matters |
| --------- | -------------- |
| Namespace (`Infra`, `Dcim`, `Ipam`, custom) | Changes every `kind` and peer reference |
| Generic inheritance (`inherit_from`) | Affects attributes, relationships, queries |
| Hierarchy (`hierarchical: true` on a generic) | Locks in a parent/child tree shape |
| Relationship cardinality and kind (Attribute / Component / Parent / Generic) | Component implies delete-cascade; wrong choice loses or keeps data unexpectedly |
| Whether an attribute is `optional`, `unique`, or part of `human_friendly_id` | Changes validation and UI behavior |
| Branch-aware behavior (`branch: agnostic` vs default) | Affects merge and diff semantics |

### How to Surface

Prefer one of these, in order:

1. **Ask**, when the choice materially changes the output
   and you have no reasonable default:
   `"Should Device inherit from a Generic like InfraNode,
   or stand alone? This affects which attributes it
   picks up."`
2. **State and invite redirect**, when a default is
   reasonable but not obvious:
   `"Using namespace 'Dcim' for the device nodes -- say
   if you'd prefer a different namespace."`
3. **Proceed**, only when the choice is trivial or
   dictated by existing code (e.g., matching a namespace
   already used in the repo).

### Anti-Patterns

- Generating a full schema with an invented namespace and
  no mention of the choice
- Picking `Attribute` for every relationship because it
  "usually works," when Component or Parent is what the
  user needs for a containment model
- Adding `hierarchical: true` to match a vaguely described
  "tree of locations" without confirming

### Prevention

Before writing the first line of YAML or Python, list the
structural choices the request leaves open. If the list
is empty, proceed. If not, surface them first.
