---
title: Open the traces of a bundle by trace ID in a local Tempo
impact: HIGH
tags: triage, traces, tempo, grafana, performance, slowness
---

## Open the traces of a bundle by trace ID in a local Tempo

Impact: HIGH

When the manifest has a `traces` entry with traces
written, read its `details`, then open the traces:
post every file of `bundle/traces/` to a local
Tempo, and open each trace in Grafana by the trace
ID in its file name, starting with `0001`. Report
which service and which operation took the time.

### Why it matters

A bundle collected with `infrahub-collect create
--include-traces` holds one file per slow request,
in OpenTelemetry (OTLP) JSON. A trace shows where
the time of one request went: each service, each
GraphQL resolver, each database query. It is the
most direct evidence of a slowness. But the files
cannot be read one by one: a trace has many spans,
and only a trace viewer shows them in parent-child
order with their durations.

The files are sorted slowest first: `0001` is the
slowest trace. A Tempo search does not return
replayed traces whose timestamps are hours or days
old, but Tempo finds each of them at once by its
trace ID (tested with Tempo 2.10.3).

### What to do

1. Read the `traces` entry of
   `bundle_information.json` first:
   - `status`: `success`, `skipped` or `failed`. A
     `skipped` or `failed` entry has a reason; report
     it as a finding.
   - `details.window` and `details.min_duration_used`:
     the time window and the shortest trace kept.
   - `details.traces_written` and
     `details.traces_left_out`: the number of traces
     in `bundle/traces/`, and how many did not fit in
     the size limit.
   - `details.sample_ratio`: the share of requests
     that has a trace. With a low ratio, a missing
     trace does not prove that a request was fast.
2. Start a local Tempo and Grafana on the analyst's
   machine, for example the observability stack of
   the Infrahub development environment. Never post
   the files to the customer's Tempo or to any
   shared instance: the traces are customer data.
3. Post each file to the OTLP HTTP receiver of that
   local Tempo:

   ```bash
   for f in bundle/traces/*.json; do
     curl -sf -X POST "http://localhost:4318/v1/traces" \
       -H "Content-Type: application/json" \
       --data-binary @"$f" || echo "rejected: $f"
   done
   ```

4. Open each trace in Grafana by the trace ID in its
   file name: `0001-<trace ID>.json`. In Explore,
   choose the Tempo data source, select TraceQL, and
   enter the trace ID. Or call the Tempo API:
   `curl -H "Accept: application/json"
   "http://localhost:3200/api/v2/traces/<trace ID>"`.
   Do not use a search to find them.
5. For each trace, report the slowest spans: the
   service (`service.name`), the operation (the span
   name, such as a GraphQL query name or a task
   name), and the duration. Cite the file name as
   evidence, like a log line.

### Compliant

```text
Traces (bundle_information.json: traces, success;
35 written, 0 left out; window 08:45-08:55 UTC;
sampling ratio 1.0, raised for the test).

Replayed into a local Tempo with POST /v1/traces,
then opened by ID in Grafana.

bundle/traces/0001-6c26f0d2e9c893ed614173cb81d8d534.json:
10.74 s in infrahub-task-worker, span "Sync Git
Repositories". The GraphQL request that started it
took 19.7 ms on infrahub-server. The time is in the
Git sync task, not in the API or the database.
```

### Non-compliant

```text
The bundle has a traces/ folder. I read
0001-6c26f0d2e9c893ed614173cb81d8d534.json: it has
many spans with startTimeUnixNano values. Load the
folder into Grafana and search for slow traces.
```

The report does not say which service or operation
took the time, and a Grafana search does not find
replayed traces that are older than a few minutes.

### Common mistakes

- Searching for the replayed traces instead of
  opening them by ID. The search returns nothing,
  and the analyst concludes that the bundle has no
  slow trace.
- Posting the files to the customer's own Tempo, or
  to a shared OpsMill instance.
- Reading the JSON files by hand and quoting raw
  timestamps instead of span durations.
- Ignoring `traces_left_out` and the sampling ratio:
  the slowest traces are in the bundle, but not
  every slow request.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/collect/create)
