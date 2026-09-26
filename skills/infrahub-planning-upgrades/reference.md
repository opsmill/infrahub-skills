# Upgrade Plan Reference

## Columns

| Column | Holds |
| ------ | ----- |
| `Change` | The change, named: what the release did, not "review the notes" |
| `Release` | The single version that introduced it, `X.Y.Z` |
| `Kind` | `breaking` when something stops working; `preparation` when the release asks for work that is not a breakage, such as moving a dependency alongside it |
| `Severity` | `critical`: Infrahub refuses to start or load until it is fixed. `warning`: the upgrade completes but something the user relies on breaks. `info`: worth knowing, nothing to fix |
| `When` | `before` the hop (a schema Infrahub will refuse must change first), `during` it (a database version that moves alongside), or `after` it (branch rebases, hardening that follows) |
| `Affected` | `yes`, `no`, or `unknown`; see [impact-verdict-needs-evidence](./rules/impact-verdict-needs-evidence.md) |
| `Evidence` | The artifact behind a `yes` or `no` |
| `Action` | What the user does, in the imperative; for `unknown`, the probe that settles it |
| `Source` | The release note, or the deprecation guide it links to |

`infrahub upgrade --check` classifies each pending
migration. One that requires a branch rebase points at
`When: during` or `after`, not `before`.

## Example

The shape to follow. The rows come from reading those
releases' notes; do not copy them into another plan
without reading the notes for its range.

```markdown
# Upgrade plan: 1.3.2 to 1.4.0

Nothing was upgraded. Each step below is for you to run,
following the upgrade guide for your deployment:
https://docs.infrahub.app/deploy-manage/maintain-upgrade/upgrade/overview

## 1.3 -> 1.4

Steps:

1. Take a backup.
2. Clear the `before` findings below.
3. Upgrade to 1.4.0.
4. Clear the `after` findings.

| Change | Release | Kind | Severity | When | Affected | Evidence | Action | Source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Overriding the peer of a generic relationship refused at schema load | 1.4.0 | breaking | critical | before | no | `grep -rn 'peer:' schemas/` shows no node redeclaring a relationship it inherits | None | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
| `IPAddressGetNextAvailable` deprecated | 1.4.0 | preparation | info | after | yes | `queries/next_ip.gql -> IPAddressGetNextAvailable` | Switch the query to `InfrahubIPAddressGetNextAvailable` | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
| `IPPrefixGetNextAvailable` deprecated | 1.4.0 | preparation | info | after | unknown | Python generators were not shared | `grep -rn 'IPPrefixGetNextAvailable' generators/` | https://github.com/opsmill/infrahub/releases/tag/infrahub-v1.4.0 |
```
