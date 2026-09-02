---
title: Verify a Kind Exists Before Inheriting or Peering It
impact: HIGH
tags: reuse, marketplace, core, generics, inherit_from, peer
---

## Verify a Kind Exists Before Inheriting or Peering It

Impact: HIGH

Three tiers of kind exist and must not be conflated:
kinds the platform ships, kinds published on the
marketplace, and kinds defined locally. Only the first
is available on a clean instance without extra loading.

### Why it matters

A widely used kind is not the same thing as a
platform-guaranteed kind. Assume otherwise and you get a
schema that loads on the developer machine where the
marketplace schema was pulled, and fails on a clean one
with a peer-not-found error naming a kind the reader
believes is built in.

That assumption also propagates. Once it reaches a
project's own guidance ("inherit from the location
generic"), every reader inherits a kind that will not
resolve on a fresh install, and the failure surfaces at
someone else's first deploy rather than at authoring
time.

### The three tiers

| Tier | Available on a clean instance | Cost |
| ---- | ---------------------------- | ---- |
| **Platform core** (a kind Infrahub itself ships) | Yes | none |
| **Marketplace-published** | **No.** Must be fetched and loaded | becomes a dependency your repository carries |
| **Locally defined** | Only if your files define it | yours to maintain |

A `Core`, `Builtin`, or `Ipam` prefix is a naming
convention, not a guarantee. `CoreLocation` reads exactly
like a platform kind and does not exist. The tier is
decided by whether Infrahub ships the kind, so confirm it
rather than reading the prefix.

The `Builtin` namespace is small. On a bare instance it
is exactly four kinds:

```text
BuiltinIPAddress    (generic)
BuiltinIPNamespace  (generic)
BuiltinIPPrefix     (generic)
BuiltinTag          (node)
```

**There is no location kind in the platform core.** The
commonly referenced location generic, `LocationGeneric`,
is published on the marketplace, not shipped by the
platform. It is the most likely kind to be mistaken for
core, because almost every example schema uses one --
including [hierarchy-setup.md](./hierarchy-setup.md) and
[display-menu-placement.md](./display-menu-placement.md)
in this skill, both of which now say so at the point of
use. `IpamVLAN` and `IpamPrefix` are the same story: the
Builtin IPAM primitives are `BuiltinIPAddress`,
`BuiltinIPNamespace` and `BuiltinIPPrefix`, and nothing
else.

### Check before you depend on it

Ask the instance rather than assuming:

```bash
# does this kind exist? works for nodes and generics alike
infrahubctl schema show <Kind>
```

`schema show` is the check that answers the question,
because it resolves generics. Reuse candidates usually
*are* generics: three of the four `Builtin` kinds above
are, and so is the location generic people reach for.

`infrahubctl schema list` is for browsing, not for
confirming. It prints node kinds only, so a generic that
exists is absent from the table and a generic that does
not exist looks identical. `infrahubctl marketplace show
<namespace>/<name>` tells you what a published schema
contains before you fetch it, which is the other half of
the question.

Do this on the **cleanest** instance the schema has to
work on, not on the machine where you have been
developing. A developer instance has accumulated
whatever was loaded during experiments.

### If it is marketplace-published rather than core

That is fine, and often the right answer. It is a
*decision*, not a detail, and it has to be recorded:

1. Fetch it properly, so the version and update path are
   preserved:

   ```bash
   infrahubctl marketplace get <namespace>/<name>
   ```

2. Commit the fetched files into the repository, so a
   clean deploy loads them before your own schema.
3. Load them **before** the schema that inherits from
   them. Order matters: the peer has to exist first.
4. Record the provenance in one comment next to the
   shape that uses it, in the format
   [reuse-evaluate-per-generic.md](reuse-evaluate-per-generic.md)
   defines. That file owns the format; this rule does not
   define a shorter one. A note that names the command
   but not the kinds vouches for nothing in particular.

   The command above takes the latest published version,
   so if you did not pass `-v`, record the date instead
   of inventing a version number:

```yaml
# Sourced from the marketplace:
#   infrahubctl marketplace get infrahub/location -v 1.4.0
# Provides: LocationGeneric, LocationSite.
# Excluded: nothing, the whole file was taken.
# Committed under schemas/vendor/ and loaded before this file.
```

See
[../../infrahub-common/marketplace-reference.md](../../infrahub-common/marketplace-reference.md)
for discovery and fetching.

### Where the provenance template lives

[reuse-evaluate-per-generic.md](./reuse-evaluate-per-generic.md)
owns the provenance comment format, including the
exclusion rationale a partial adoption needs. This rule
requires the same header; it does not define a second,
shorter one. If you took only part of a file, write the
full form there.

### Reading examples correctly

Examples in these rules and elsewhere name specific
kinds to be concrete, not to promise availability. A
kind appearing in an example is evidence that it is a
sensible shape, not evidence that it exists on your
instance. When an example names a kind you are about to
depend on, check its tier first.

### Common mistakes

- Treating a kind as core because every example uses it.
  Popularity is not availability.
- Reading the namespace prefix as the tier. `Core`,
  `Builtin`, and `Ipam` are conventions a made-up kind can
  spell just as well.
- Confirming with `infrahubctl schema list`, which prints
  node kinds only and so cannot see the generic you are
  about to inherit.
- Verifying on a developer instance that already has the
  marketplace schema loaded, which proves nothing about a
  clean one.
- Copying schema YAML out of a GitHub repository instead
  of fetching from the marketplace. That works once and
  loses the version and the update path.
- Inheriting a marketplace kind without committing the
  fetched files, so CI and every teammate fail while the
  author's machine works.

Reference: [Infrahub Schema Docs](https://docs.infrahub.app)
