# infrahub-sync Config Reference

Commands and config keys that `SKILL.md` points at. They
were read on the infrahub-sync `main` branch at commit
`e509abbb`.

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

- Source credentials come from environment variables,
  not from the file. The adapter's example lists the ones
  it reads.
- The Infrahub address, token and branch are read in two
  places that do not agree:
  - `generate` takes `url`, `token` and `branch` from
    `destination.settings` only. It ignores
    `INFRAHUB_API_TOKEN`, so without a `token` in the
    settings it reads the schema anonymously.
  - `diff` and `sync` use `INFRAHUB_ADDRESS` (or
    `INFRAHUB_URL`) and `INFRAHUB_API_TOKEN` first, and
    the settings only when those are unset.
  - A `branch` in `destination.settings` overrides
    `--branch` on all three commands.

  The live validation below runs from a run config that
  sets all three, so every command reads the same
  Infrahub branch.
- `order` is optional on `main`. infrahub-sync computes
  the write order from the `reference` of each field.
  Set `order` only to override it.
- A `reference` is resolved twice. The source adapter
  looks the peer up among the records it loaded for the
  referenced kind, so that kind needs its own
  `schema_mapping` entry: the NetBox adapter, for
  example, raises `Unable to locate the node ...` when the
  peer was not loaded, even if Infrahub already holds it.
  Infrahub then needs the peer node on the branch. Read
  how the adapter's `obj_to_diffsync` (or its equivalent)
  resolves a reference before relying on nodes that are
  only in Infrahub.

## Live validation commands

Run from the customer repository. The commands use a run
config, `sync/<project>/config.run.yml`: a copy of
`config.yml` that stays out of Git and sets the Infrahub
`url`, the test `branch` and, when `generate` needs it,
the `token` (see
[the config keys](#config-keys-on-main)). Generated files
land in `sync/<project>/`, next to the run config, as
they would with `--name`.

```bash
grep -qxF ".infrahub-sync-cache/" .gitignore || echo ".infrahub-sync-cache/" >> .gitignore
grep -qxF "config.run.yml" .gitignore || echo "config.run.yml" >> .gitignore

infrahubctl branch create "<test-branch>"
infrahubctl schema load schemas --branch "<test-branch>"

RUN="sync/<project>/config.run.yml"
cp sync/<project>/config.yml "$RUN"
# Edit $RUN: under destination.settings set url to the Infrahub address
# and branch to <test-branch>. Add token only if generate fails to authenticate.

# Show the effective target, and stop when the commands would not agree.
python - "$RUN" <<'EOF'
import os, sys, yaml
settings = yaml.safe_load(open(sys.argv[1]))["destination"].get("settings") or {}
url, branch = str(settings.get("url") or ""), settings.get("branch")
env = os.environ.get("INFRAHUB_ADDRESS") or os.environ.get("INFRAHUB_URL") or ""
print(f"generate reads the schema from {url} on branch {branch}")
print(f"diff and sync use {env or url} on branch {branch}")
if not branch:
    sys.exit("no destination branch in the run config: stop")
if env and env.rstrip("/") != url.rstrip("/"):
    sys.exit("INFRAHUB_ADDRESS and destination.settings.url differ: stop")
EOF

infrahub-sync generate --config-file "$RUN"
infrahub-sync diff --config-file "$RUN"

# Approval point 2. Only after the user approves:
infrahub-sync sync --config-file "$RUN"

# Expect no creates or updates, except for records changed in the source since the sync.
infrahub-sync diff --config-file "$RUN"

rm "$RUN"   # it may hold the Infrahub token
```

When the adapter comes from an infrahub-sync checkout
that is not released yet, for example one handed over by
`infrahub-building-sync-adapters`, prefix each
`infrahub-sync` command with
`uv run --project "<infrahub-sync-checkout>"`. That uses
the checkout without changing the customer repository's
dependencies.

`generate`, `diff` and `sync` also take `--branch` on
infrahub-sync `main`, but a `branch` in
`destination.settings` overrides it. That is why the
branch goes in the run config, and why the committed
`config.yml` carries no test branch.

`sync` reads the source again and computes its own diff
before writing. It writes the current source data, which
includes any record created or changed after the `diff`
the user approved.

The cache holds snapshots of source data, which is why
`.infrahub-sync-cache/` goes into `.gitignore` before the
first run.

## Known infrahub-sync core limits

Warn the user about these, and draft an issue with
`infrahub-reporting-issues` instead of working around
them in infrahub-sync core:

- One bad record stops the whole run. With
  `--continue-on-error`, the Infrahub adapter skips a
  peer relationship whose peer has empty identifier
  values and a node it cannot build into a model, and
  logs a warning for each. The flag does not skip a
  failed write to Infrahub, a duplicate key, or a source
  adapter error. The data pre-check in
  [rules/mapping-identifiers-match-hfid.md](./rules/mapping-identifiers-match-hfid.md)
  finds those records before the first run.
- A record removed from the source stays in Infrahub.
  With no `diffsync_flags` in the config, infrahub-sync
  uses `SKIP_UNMATCHED_DST`, so the diff shows no row for
  a node that only Infrahub holds. With flags that let
  the diff show a deletion, `sync` still leaves the node,
  because `InfrahubModel` implements `create` and
  `update` only.
- Transforms render with Jinja's native types, so a
  number-like string (`"1411"`) becomes a number. Add
  `| tojson` to a transform whose result must stay a
  string.
- An optional attribute marked `unique: true` fails as
  soon as two nodes leave it empty.
