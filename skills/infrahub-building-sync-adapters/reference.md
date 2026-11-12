# infrahub-sync Source Adapter Reference

Formats and phase details that `SKILL.md` points at.
The contract facts below were read on the infrahub-sync
`main` branch at commit `139df64f`.

## API behavior file (`api-behavior.yml`)

Phase 1 writes it from the captures, and the spec,
the test fakes and the retry policy read it. Keep it in
the spec directory of the infrahub-sync checkout
(`dev/specs/<NNN>-<name>/api-behavior.yml`).

The file is a mapping with one top-level key,
`endpoints`: a list with one entry per endpoint the
sync reads, including endpoints read only to resolve a
reference (a sites endpoint that devices point at). Every
entry carries all twelve keys below, so a reader can
tell "not observed" from "forgotten".

| Key | Value | Read it from |
| --- | ----- | ------------ |
| `path` | The endpoint path without the query string. A full URL is accepted. | The captured request |
| `method` | The HTTP method, `GET` for a source | The captured request |
| `pagination` | A mapping, see [`pagination`](#pagination) | The captured next link |
| `required_headers` | Headers a request fails without, beyond authentication. `[Accept]` when nothing else is needed. | A capture sent without the header |
| `default_fields` | `all`, or the list of fields a request without field selection returns | A capture without field selection |
| `field_selection` | The query parameter that selects fields (`fields`, `$select`), or `none` | A capture with field selection |
| `filters_supported` | The server-side filter parameters that were tried and worked | Captures with a filter |
| `rate_limit` | A mapping, see [`rate_limit`](#rate_limit) | A throttled capture, or the rate-limit headers on any capture |
| `empty_result_is_valid` | `true` when an empty list is a legitimate answer; `false` when the endpoint always has rows, so an empty page means the read failed | A capture of an empty result |
| `captures` | The capture files this entry is based on | — |
| `field_quirks` | A mapping, see [`field_quirks`](#field_quirks) | The captured rows |
| `subclass_rows` | `none`, or `{discriminator: <field>}` when the endpoint also returns rows of sub-types, told apart by that field | The captured rows |

### `pagination`

| Key | Value |
| --- | ----- |
| `type` | `link_header` (a `Link` header with `rel="next"`), `body_link` (a next URL in the body, such as `@odata.nextLink`), `offset` (the client computes the next offset), `cursor`, or `none` |
| `next_link_carries` | Every query parameter the captured next link repeats, except the one that moves the page (`offset`, `cursor`). Copy it from the captured link, not from the documentation. `[]` only when the captured link really carries no other parameter. |
| `cursor_param` | Optional. The parameter that moves the page. |
| `total_header` | Optional. A header that gives the total row count. |

Select the next link by its relation exactly. Some APIs
send `first`, `prev`, `next` and `last` together, and a
`prev` link can carry a negative offset.

### `rate_limit`

| Key | Value |
| --- | ----- |
| `status` | The status of a throttled response, for example `429` |
| `retry_after_header` | `true` when the throttled response carries `Retry-After`, otherwise `false` |
| `reset_header` | Optional. The header that gives the time the limit resets, for example `X-RateLimit-Reset` |
| `limit_header` | Optional. The header that gives the limit, for example `X-RateLimit-Limit` |
| `max_retry_after` | Optional. Replaces the 300 s default in [rules/retry-default-policy.md](./rules/retry-default-policy.md). Set it only after the user approves a longer wait. |
| `retry_statuses` | Optional. Replaces the default retried statuses when the captures show the API throttles with another status. |

When no throttled response was captured, write
`rate_limit: {observed: false}`, with any rate-limit
headers the captures carry. The default retry policy
then applies unchanged.

### `field_quirks`

A fixed vocabulary, so the test fakes can apply it
without interpretation:

| Key | Values |
| --- | ------ |
| `reference_set` | `object` when a reference field comes back as an object (`{"id": ..., "href": ...}`); `id` when it comes back as a bare ID string |
| `reference_empty` | `empty_string` when an empty reference comes back as `""`; `null`; or `absent` when the field is missing from the row |
| `unknown_selected_field` | `dropped_silently` when a field-selection parameter naming a field the endpoint lacks is ignored, with HTTP 200 and no error; `error` when the API rejects the request (record the status in the spec) |
| `value_types` | Optional. The type values come back as, for one field or for all, for example `string` when numbers come back as strings |

### Example

An invented inventory API. The values are illustrations
of the format, not facts about any product.

```yaml
endpoints:
  - path: /api/v2/devices
    method: GET
    pagination:
      type: link_header
      cursor_param: offset
      next_link_carries: [limit, fields, filter]
      total_header: X-Total-Count
    required_headers: [Accept]
    default_fields: all
    field_selection: fields
    filters_supported: [filter]
    rate_limit:
      status: 429
      retry_after_header: true
      reset_header: X-RateLimit-Reset
    empty_result_is_valid: true
    captures: [devices_page1.json, devices_page2.json, devices_unknown_field.json, devices_429.json]
    field_quirks:
      reference_set: object
      reference_empty: empty_string
      unknown_selected_field: dropped_silently
      value_types: string
    subclass_rows: {discriminator: device_class}
  - path: /api/v2/sites
    method: GET
    pagination:
      type: link_header
      cursor_param: offset
      next_link_carries: [limit, fields]
    required_headers: [Accept]
    default_fields: all
    field_selection: fields
    filters_supported: []
    rate_limit: {observed: false}
    empty_result_is_valid: false
    captures: [sites_page1.json, sites_page2.json]
    field_quirks:
      reference_set: object
      reference_empty: empty_string
      unknown_selected_field: dropped_silently
    subclass_rows: none
```

## Captures

One JSON file per response, with the request, the
status, every response header and the body:

```json
{
  "request": {"method": "GET", "path": "/api/v2/devices?limit=2&fields=id,name,site&filter=status%3Dactive"},
  "status": 200,
  "headers": {
    "Content-Type": "application/json",
    "Link": "<https://inventory.example.net/api/v2/devices?limit=2&fields=id,name,site&filter=status%3Dactive&offset=2>; rel=\"next\"",
    "X-Total-Count": "3"
  },
  "body": {"items": [{"id": "d-0001", "name": "edge-01", "site": {"id": "s-01", "href": "https://inventory.example.net/api/v2/sites/s-01"}}]}
}
```

Replacing customer values before a capture enters a
repository:

- Replace hostnames with an `example` host, and names,
  email addresses, IDs, site codes and free text with
  invented values.
- Replace each real value with the same invented value
  everywhere, so references between captures still
  resolve.
- Keep shapes, types and empty values unchanged. An
  empty string stays `""`, a number sent as a string
  stays a string.
- Keep the raw responses out of every repository. The
  redacted copies go to `tests/fixtures/<name>/` in the
  infrahub-sync checkout.
- Before each commit, search the diff for the customer's
  name, domain and record IDs.

## Phase 0: preflight details

Run these in the infrahub-sync checkout and in the
customer repository. Stop at the first failure and tell
the user what failed.

```bash
# The checkout follows the main contract. A match means the
# feature/v3-develop contract: stop and tell the user.
grep -rn "BUILTIN_ADAPTER_CAPABILITIES" infrahub_sync/

# Infrahub is reachable and the token is in the environment.
test -n "$INFRAHUB_API_TOKEN" && echo "INFRAHUB_API_TOKEN is set"
infrahubctl info
```

- **Contract.** Create the adapter branch from
  `origin/main`. The `feature/v3-develop` contract
  (`BUILTIN_ADAPTER_CAPABILITIES`, planned writes) is not
  covered by this skill.
- **API login with the integration account.** Send one
  read of one record with the account the sync will use,
  and expect HTTP 200. Some systems refuse Basic
  authentication for interactive or admin accounts and
  accept it only for service accounts, so an account
  that works in the web interface can still get 401.
  Ask the user for the integration account instead of
  testing with an admin account.
- **Adapter name.** One lowercase word with no `-` and
  no `_`: `netbox`, `peeringmanager`, `genericrestapi`.
  The generated class name and the class the loader
  looks for agree only for a single lowercase word. Add
  a `sync` suffix when the name equals the vendor SDK's
  import name (`ipfabricsync`, `slurpitsync`,
  `msgraphsync`), because the generated package directory
  is put on `sys.path` and would hide the SDK.

## Adapter contract on `main`

- One module, `infrahub_sync/adapters/<name>.py`, with
  two classes:
  - `<Name>Adapter(DiffSyncMixin, Adapter)`, with a `type`
    class attribute equal to the configuration name
    ignoring case, an
    `__init__(self, target, adapter, config, *args, **kwargs)`
    that calls `super().__init__(*args, **kwargs)`, and a
    `model_loader(self, model_name, model)`.
  - `<Name>Model(DiffSyncModelMixin, DiffSyncModel)`.
    A source-only model raises `NotImplementedError` from
    `create`, `update` and `delete` instead of reporting
    success.
- `super().__init__(*args, **kwargs)` forwards
  `internal_storage_engine`; leaving it out breaks the
  store.
- Define exactly one `Adapter` subclass and one
  `DiffSyncModel` subclass per module: the loader takes
  the first matching class it finds. An HTTP client class
  that subclasses neither can sit in the same module.
- If the module fails to import (a missing SDK, for
  example), `infrahub-sync generate` still succeeds and
  falls back to a plain `DiffSyncModel`. The error shows
  up later, so import the module in a unit test.
- Apply filters and transforms only on the source side,
  with `self.target == "source"`.
- Every record passed to the model carries `local_id`,
  the source's primary key as a string.
- Read a static field with `if field.static is not None`,
  so `0`, `false` and `""` survive.
- Keep the default `cursor_tier_for`, which returns
  `CursorTier.NONE`: every run reads the source in full.
- When `empty_result_is_valid` is `false` for an
  endpoint, raise on an empty page or a body without the
  row list instead of returning zero rows. Zero rows
  reads as "every record was removed" in the diff.

Reference adapters on `main`: `netbox.py` for the
contract shape, `aci.py` for a `requests.Session` client
with retries, `peeringmanager.py` for a thin subclass of
the generic REST adapter. The Webex adapter in
[opsmill/infrahub-sync#401](https://github.com/opsmill/infrahub-sync/pull/401)
is the only example that follows `Link` headers and
honors `Retry-After`; it is not merged.

## Phase 2: spec details

Write the spec in the infrahub-sync checkout under
`dev/specs/<NNN>-<name>/spec.md`, next to
`api-behavior.yml`.

- Cite the behavior file entry for every endpoint the
  adapter reads, for example
  "`api-behavior.yml`, endpoint `/api/v2/devices`".
- Where the captures and the vendor documentation
  disagree, follow the captures and name the
  disagreement in the spec.
- Give every requirement a number in one table, so the
  final audit in phase 6 can mark each one:

| ID | Requirement | Source | Test |
| -- | ----------- | ------ | ---- |
| FR-001 | Follow the `rel="next"` link until it is absent, sending it as captured | `api-behavior.yml`, `/api/v2/devices`, `pagination` | `test_pagination_follows_captured_next_link` |
| FR-002 | Stop with an error when `Retry-After` asks for more than 300 s | Default retry policy | `test_long_retry_after_stops_the_run` |

## Phase 5: live validation commands

Run from the customer repository. `uv run --project`
uses the adapter from the infrahub-sync checkout without
changing the customer repository's dependencies.
`generate` reads the schema from Infrahub, so point it at
the branch where the schema is loaded.

```bash
grep -qxF ".infrahub-sync-cache/" .gitignore || echo ".infrahub-sync-cache/" >> .gitignore

infrahubctl branch create "<test-branch>"
infrahubctl schema load schemas --branch "<test-branch>"

uv run --project "<infrahub-sync-checkout>" infrahub-sync list --directory sync
uv run --project "<infrahub-sync-checkout>" infrahub-sync generate --name "<project>" --directory sync
uv run --project "<infrahub-sync-checkout>" infrahub-sync diff --name "<project>" --directory sync --branch "<test-branch>"

# Approval point 4. Only after the user approves:
uv run --project "<infrahub-sync-checkout>" infrahub-sync sync --name "<project>" --directory sync --branch "<test-branch>"

# Expect no changes.
uv run --project "<infrahub-sync-checkout>" infrahub-sync diff --name "<project>" --directory sync --branch "<test-branch>"
```

`diff` and `sync` take `--branch` on infrahub-sync
`main`. Pass it on the command line rather than
setting a branch in the destination settings, so no
test branch ends up in the committed configuration.

The cache holds snapshots of source data, which is why
`.infrahub-sync-cache/` goes into `.gitignore` before the
first run.

## Known infrahub-sync core limits

Warn the user about these, and draft an issue instead of
fixing them (see
[rules/scope-adapter-files-only.md](./rules/scope-adapter-files-only.md)):

- One bad record stops the whole run, and
  `--continue-on-error` does not help. The data
  pre-check in
  [rules/mapping-identifiers-match-hfid.md](./rules/mapping-identifiers-match-hfid.md)
  finds those records before the first run.
- `InfrahubModel` has no delete. A record removed from
  the source shows as a deletion in the diff but stays in
  Infrahub. Say so in the adapter's docs page.
- Transforms render with Jinja's native types, so a
  number-like string (`"1411"`) becomes a number. Add
  `| tojson` to a transform whose result must stay a
  string.
- An optional attribute marked `unique: true` fails as
  soon as two nodes leave it empty.
