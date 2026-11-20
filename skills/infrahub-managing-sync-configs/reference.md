# infrahub-sync Config Reference

Commands and config keys that `SKILL.md` points at. They
were read on the infrahub-sync `main` branch at commit
`bdf58f98`.

## Preflight commands

Run these in the customer repository, in the environment
where infrahub-sync is installed. Stop at the first
failure and tell the user what failed.

```bash
# The installed infrahub-sync follows the main contract. A match means the
# feature/v3-develop contract: stop and tell the user.
grep -rn "BUILTIN_ADAPTER_CAPABILITIES" "$(python -c 'import infrahub_sync, os; print(os.path.dirname(infrahub_sync.__file__))')"

# The source system has an adapter: its module is in the installed package.
ls "$(python -c 'import infrahub_sync, os; print(os.path.dirname(infrahub_sync.__file__))')/adapters/"

# Infrahub is reachable and the token is in the environment.
test -n "$INFRAHUB_API_TOKEN" && echo "INFRAHUB_API_TOKEN is set"
infrahubctl info
```

The adapters on `main` are `aci`, `genericrestapi`,
`infrahub`, `ipfabricsync`, `msgraphsync`, `nautobot`,
`netbox`, `peeringmanager`, `prometheus`, `slurpitsync`
and `webex`. `source.name` in the config is the module
name. A source that is not in the list, or a request
for a new endpoint, goes to
`infrahub-building-sync-adapters`.

## Config keys on main

The keys below are the ones in
[`examples/netbox_to_infrahub/config.yml`](https://github.com/opsmill/infrahub-sync/blob/main/examples/netbox_to_infrahub/config.yml).
Read the example of the same adapter under
[`examples/`](https://github.com/opsmill/infrahub-sync/tree/main/examples)
before writing a new config.

```yaml
name: from-netbox                 # the project name passed to --name
source:
  name: netbox                    # the adapter module name
  settings:
    url: "https://netbox.example.com"
destination:
  name: infrahub
  settings:
    url: "http://localhost:8000"
schema_mapping:
  - name: LocationSite            # destination kind
    mapping: dcim.sites           # source resource
    identifiers: ["name"]         # see rules/mapping-identifiers-match-hfid.md
    fields:
      - name: name                # destination attribute or relationship
        mapping: slug             # source field
      - name: tags
        mapping: tags
        reference: BuiltinTag     # a relationship: the peer's kind
```

- Credentials come from environment variables, not
  from the file. The adapter's example lists the ones it
  reads.
- `order` is optional on `main`. infrahub-sync computes
  the write order from the `reference` of each field.
  Set `order` only to override it.
- Every kind named in `reference` needs its own
  `schema_mapping` entry, or nodes already in Infrahub
  for it.

## Live validation commands

Run from the customer repository. `generate` reads the
schema from Infrahub, so point it at the branch where the
schema is loaded.

```bash
grep -qxF ".infrahub-sync-cache/" .gitignore || echo ".infrahub-sync-cache/" >> .gitignore

infrahubctl branch create "<test-branch>"
infrahubctl schema load schemas --branch "<test-branch>"

infrahub-sync list --directory sync
infrahub-sync generate --name "<project>" --directory sync --branch "<test-branch>"
infrahub-sync diff --name "<project>" --directory sync --branch "<test-branch>"

# Approval point 2. Only after the user approves:
infrahub-sync sync --name "<project>" --directory sync --branch "<test-branch>"

# Expect no creates or updates, except for records changed in the source since the sync.
# Deletions of nodes the source does not hold are expected.
infrahub-sync diff --name "<project>" --directory sync --branch "<test-branch>"
```

When the adapter comes from an infrahub-sync checkout
that is not released yet, for example one handed over by
`infrahub-building-sync-adapters`, prefix each
`infrahub-sync` command with
`uv run --project "<infrahub-sync-checkout>"`. That uses
the checkout without changing the customer repository's
dependencies.

`generate`, `diff` and `sync` take `--branch` on
infrahub-sync `main`. Pass it on the command line rather
than setting a branch in the destination settings, so no
test branch ends up in the committed configuration.

The cache holds snapshots of source data, which is why
`.infrahub-sync-cache/` goes into `.gitignore` before the
first run.

## Known infrahub-sync core limits

Warn the user about these, and draft an issue with
`infrahub-reporting-issues` instead of working around
them in infrahub-sync core:

- One bad record stops the whole run, and
  `--continue-on-error` does not help. The data
  pre-check in
  [rules/mapping-identifiers-match-hfid.md](./rules/mapping-identifiers-match-hfid.md)
  finds those records before the first run.
- `InfrahubModel` has no delete. A record removed from
  the source shows as a deletion in the diff but stays in
  Infrahub.
- Transforms render with Jinja's native types, so a
  number-like string (`"1411"`) becomes a number. Add
  `| tojson` to a transform whose result must stay a
  string.
- An optional attribute marked `unique: true` fails as
  soon as two nodes leave it empty.
