---
title: impact-verdict-needs-evidence
impact: CRITICAL
tags: impact, evidence, verdict, affected
---

# Rule: impact-verdict-needs-evidence

## The rule

Every finding gets an `Affected` verdict of `yes`, `no`,
or `unknown`. A `yes` or `no` names the artifact that
proves it. An `unknown` names the probe that would
settle it.

## Why it matters

A generic list of breaking changes is the release notes
again, and the user already has those. The value of the
plan is the verdict: which of these changes hit this
repository. "May apply to your setup" hands the work
back, and a `yes` with nothing behind it cannot be
checked, so the user cannot tell a real blocker from a
guess before the window opens.

## How to apply

1. Check each change against the repository inventory
   from step 3, and against the instance when one is
   reachable.
2. For `yes` or `no`, put something locatable in
   `Evidence`, strongest first:
   - a file path, ideally with the element:
     `queries/next_ip.gql -> IPAddressGetNextAvailable`
   - a schema kind or `Kind.attribute`
   - a query and its result: ``query_graphql `{ BuiltinIPAddress { count } }` returned 0``
   - a probe and its output: `infrahub upgrade --check` listing 2 pending migrations
3. Use `unknown` when the evidence is not in hand, for
   example a schema the user did not share. Then the
   `Action` names the probe that would decide it: an
   MCP read (`get_schema`, `get_nodes`,
   `query_graphql`), `infrahubctl info`,
   `infrahub db showmigrations`, a `grep` over the
   named files, or a named file to read. Lead with the
   probe, then the remedy: "if SSO is configured, do X"
   leaves the user unable to tell whether it is, so say
   where to look first. Name the place by name:
   `docker-compose.yml` or the Helm `values.yaml`, not
   "your deployment file" or "the server env". The
   user may not know which file holds the setting,
   which is why they need the plan to say. `unknown`
   with a probe is honest; a guessed `yes` or `no` is
   not.
4. A change that reaches every deployment, such as a
   data migration, still needs evidence for `yes`: the
   probe that shows it pending here, like
   `infrahub upgrade --check` listing the migration.
   Without a probe it is `unknown`, with that probe as
   the `Action`. "The release applies it everywhere" is
   the release note again, not evidence about this
   deployment.
5. Write the bare value. The column holds `yes`, `no`,
   or `unknown`, not a sentence.
6. Make each row stand on its own. "Same as the row
   above" leaves this row with no evidence or probe of
   its own, and rows get read, sorted, and copied one
   at a time.

## Examples

Compliant: a decided verdict with its artifact, and an
undecided one with its probe.

```markdown
| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `IPAddressGetNextAvailable` deprecated | 1.4.0 | preparation | info | after | yes | `queries/next_ip.gql -> IPAddressGetNextAvailable` | Switch the query to `InfrahubIPAddressGetNextAvailable` | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
| Overriding the peer of a generic relationship refused at schema load | 1.4.0 | breaking | critical | before | unknown | The generics these nodes inherit from were not shared | Run `get_schema` and compare each inherited relationship's peer with the generic's | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
```

Non-compliant: evidence that restates the finding, and
a verdict that is not one.

```markdown
| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `IPAddressGetNextAvailable` deprecated | 1.4.0 | preparation | info | after | yes | Your queries use the deprecated mutation | Update them | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
| Generic relationship peer overrides refused | 1.4.0 | breaking | critical | before | may apply | | Review your schema | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
```

## Common mistakes

- Evidence that repeats the change in other words.
- `unknown` with an `Action` of "review" or "check",
  which names no probe.
- `unknown` with an `Action` that starts "if you use
  X", which names the condition but not how to test it.
- Leaving `Affected` blank for a change that does not
  apply. That is a `no`, with the evidence that it does
  not apply.
- Advice with no evidence, such as a backup reminder,
  marked `yes`. General preparation is prose in the hop
  steps, not a finding.
