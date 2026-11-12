---
title: Capture the Live API and Record Its Behavior Before the Spec
impact: CRITICAL
description: >-
  Before any spec, query the source system's live API with the integration
  account, save the raw responses with their headers and pagination links,
  and write api-behavior.yml from those captures: one entry per endpoint with
  the fixed key set. Captures win over vendor documentation.
tags: probe, captures, api-behavior, pagination, rate-limit, spec
---

## Capture the Live API and Record Its Behavior Before the Spec

Query the customer's live API first, save what it
answers, and write `api-behavior.yml` from those
captures. The spec, the test fakes and the retry policy
are built on that file, not on the vendor
documentation.

### Why it matters

Documentation describes the API the vendor intends. The
adapter meets the API the customer runs. Both adapters
this skill comes from were specified from documentation,
and both broke on behavior only the live system showed:

- **Microsoft Graph (Entra ID).** Five behaviors appeared
  only against the real tenant: `startswith` ignores
  case, `not` needs an advanced query, the
  `/microsoft.graph.user` cast needs
  `ConsistencyLevel: eventual` and `$count`, a read
  without `$select` returns only 11 default properties,
  and some pages took longer than 60 s.
- **Webex.** The adapter was built against the wrong
  spec, then audited and reworked. Its real next-page
  links always carry `orgId`; the hand-written test
  pages did not, so the bug reached the live run.

A short session of read-only requests finds these before
any code depends on them.

### How to apply

1. **Use the integration account**, the one the sync
   will run as. Permissions, visible fields and the
   accepted authentication methods can differ from an
   admin account.
2. **Send read-only requests**, for every endpoint the
   sync reads, including endpoints read only to resolve
   references:
   - the first page, with the field selection and
     filters the adapter will send;
   - the next page, by following the next link exactly
     as it came back;
   - one request without field selection, to see the
     default fields;
   - one request whose field selection names a field
     that does not exist, to see whether the API drops it
     or rejects the request;
   - one filter that matches nothing, to see an empty
     result;
   - a throttled response, if one occurs. Do not provoke
     one on a production system; record the rate-limit
     headers the other responses carry.
3. **Save each response under `captures/`**: the request,
   the status, every header (the `Link` header and the
   rate-limit headers included) and the body. The file
   format is in [../reference.md](../reference.md#captures).
   Keep the raw files out of every repository. Replace
   customer values with invented ones, as
   [../reference.md](../reference.md#captures) describes,
   before a copy enters a public repository.
4. **Write `api-behavior.yml`** with a top-level
   `endpoints:` list and one entry per endpoint. Every
   entry carries the twelve keys defined in
   [../reference.md](../reference.md#api-behavior-file-api-behavioryml),
   including `pagination` (with `type` and
   `next_link_carries`), `rate_limit` (with `status` and
   `retry_after_header`) and `field_quirks` (with
   `reference_set`, `reference_empty` and
   `unknown_selected_field`).
5. **Take every value from the captures.** Read
   `next_link_carries` from the captured `rel="next"`
   URL: list every query parameter it repeats, except
   the one that moves the page. When the captures and the
   documentation disagree, the captures win, and the
   spec names the disagreement.
6. **Cite the file from the spec.** Each endpoint in the
   spec points at its entry in `api-behavior.yml`.

Show the user the file before writing the spec: it is
approval point 1.

### Correct

The captured first page of `/api/v2/devices` returned
`Link: <https://inventory.example.net/api/v2/devices?limit=2&fields=id,name,site&filter=status%3Dactive&offset=2>; rel="next"`,
rows where `site` is `{"id": ..., "href": ...}` or `""`,
and a capture with `fields=id,nmae` returned HTTP 200
with only `id`:

```yaml
endpoints:
  - path: /api/v2/devices
    method: GET
    pagination:
      type: link_header
      cursor_param: offset
      next_link_carries: [limit, fields, filter]
    required_headers: [Accept]
    default_fields: all
    field_selection: fields
    filters_supported: [filter]
    rate_limit: {status: 429, retry_after_header: true, reset_header: X-RateLimit-Reset}
    empty_result_is_valid: true
    captures: [devices_page1.json, devices_page2.json, devices_unknown_field.json, devices_429.json]
    field_quirks:
      reference_set: object
      reference_empty: empty_string
      unknown_selected_field: dropped_silently
    subclass_rows: none
```

### Incorrect

Filled in from the documentation, which says paging is
"plain offset and limit". The file exists, but the next
link's parameters, the throttled response and the field
shapes are missing, and the sites endpoint the devices
reference has no entry:

```yaml
endpoints:
  - path: /api/v2/devices
    method: GET
    pagination:
      type: offset
      next_link_carries: []
    rate_limit: {}
    field_quirks: {}
```

### Common mistakes

- **Writing the file from the documentation.** An empty
  `next_link_carries` while the captured link repeats
  `limit`, `fields` and `filter` is the sign.
- **Reading the wrong link.** Some APIs send `first`,
  `prev`, `next` and `last` together. Select
  `rel="next"` exactly.
- **Leaving out an endpoint** read only for references,
  such as the sites a device points at.
- **Normalizing field shapes.** Write down that an empty
  reference is `""` and a set one is an object, rather
  than describing the shape the documentation shows.
- **Committing raw captures**, or capturing with an
  admin account the sync will never use.

Reference: [infrahub-sync repository](https://github.com/opsmill/infrahub-sync)
