---
title: Read the trace files of a bundle and find where the time went
impact: HIGH
tags: triage, traces, spans, performance, slowness
---

## Read the trace files of a bundle and find where the time went

Impact: HIGH

When the manifest has a `traces` entry with traces
written, read its `details`, then read the files of
`bundle/traces/` directly, from `0001` (the
slowest). For each trace, find the spans that took
the time, and report the service, the operation and
the duration, with the file name as evidence. No
trace viewer is needed.

### Why it matters

A bundle collected with `infrahub-collect create
--include-traces` holds one file per slow request.
A trace shows where the time of one request went:
each service, each GraphQL query, each database
query. It is the most direct evidence of a slowness,
and the logs often show no error at all.

The files are small JSON documents, sorted slowest
first, so they can be read like any other bundle
file. Starting a trace viewer only to look at them
needs Docker and time, and adds nothing to the
analysis.

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
2. Read each file `NNNN-<trace ID>.json`, from
   `0001`. The format is OpenTelemetry (OTLP) JSON:
   - `resourceSpans[].resource.attributes`: the
     `service.name` of the spans below it, such as
     `infrahub-server` or `infrahub-task-worker`.
   - `resourceSpans[].scopeSpans[].spans[]`: each
     span, with `name` (the operation), `spanId`,
     `parentSpanId`, `startTimeUnixNano` and
     `endTimeUnixNano`, and `attributes` such as
     `query_name` for a database query or `operation`
     for a GraphQL request.
   - The duration of a span is `endTimeUnixNano`
     minus `startTimeUnixNano`, in nanoseconds.
3. Find where the time went:
   - The root span (no `parentSpanId`) is the whole
     request or task.
   - The self time of a span is its duration minus
     the time its direct children cover. Count time
     where children overlap once, since children can
     run in parallel. A large
     self time means the time went into work that is
     not traced, such as a Git operation or a call to
     an external system. A large child means the time
     went into that child, such as a database query.
   - Across all traces, add up the self time per
     service, to say which service takes most of the
     time.
   - For a large file or many traces, read the files
     with a short script (`jq` or Python) rather than
     by eye, and say that the numbers come from it.
4. Report, for each trace that matters: the file
   name, the root operation and its duration, and
   the spans that took the time, with service,
   operation and duration. Then the service that
   takes most of the time across the traces.
5. Stay on the bundle files. Do not start, query or
   post to a Tempo, Grafana, Prometheus or the
   Infrahub API, not even a local one: the answer
   must come from the files, and the traces are
   customer data. Outside the bundle, the skill
   reads only the `opsmill/infrahub` issues and
   `docs.infrahub.app` (see
   [scope-read-only-analysis.md](scope-read-only-analysis.md)).

### Ask for a richer next bundle

When the traces cannot answer the question, say in
the report's recommendations what the next bundle
needs, and hand the collection back to
`infrahub-collecting-diagnostics`. The analysis
applies none of these itself.

- The symptom is a slowness and the manifest has no
  `traces` entry, or it is `skipped` with the reason
  `not requested`: collect again with
  `--include-traces` and a window that covers the
  slowness (`--traces-since` for a slowness still
  going on, `--traces-start` and `--traces-end` for
  one that ended).
- The `traces` entry is `skipped` for another
  reason, such as Tempo not found or a missing
  Kubernetes permission: quote the reason, and name
  what fixes it (the observability stack,
  `--traces-tempo-url`, or the permission).
- Few traces and a low sampling ratio, and the
  slowness can be reproduced: a user with the
  `super_admin` permission raises the ratio for a
  limited time, the user reproduces the slowness,
  collects again, and then removes the raised ratio.
- `traces_left_out` is above 0: collect again with a
  larger `--traces-max-size`.
- The slowness happened outside `details.window`:
  collect again with a window that covers it.

### Compliant

```text
Traces (bundle_information.json: traces, success;
35 written, 0 left out; window 08:45-08:55 UTC;
sampling ratio 1.0, raised for the test).

bundle/traces/0001-6c26f0d2e9c893ed614173cb81d8d534.json:
root span "Sync Git Repositories" on
infrahub-task-worker, 10.74 s. Its children take
about 21 ms: one database query (node_get_list,
1 ms) and one API call (POST on infrahub-server,
19.7 ms). The self time is 10.72 s, so the time is
in the Git sync work itself, which has no span, not
in the API or the database.
```

### Non-compliant

```text
The bundle has 35 traces. Start Tempo and Grafana,
load the folder, and search for traces longer than
1s to see what was slow.
```

The report does not say which service or operation
took the time, and it sends the analysis to a
service outside the bundle instead of reading the
files.

### Common mistakes

- Naming the slowest span without its self time. A
  10 s request whose 10 s child is a database query
  points at the database; a 10 s span whose children
  take 20 ms points at untraced work in that span.
- Reading only `0001`. The slowest trace can be an
  outlier; the other traces show whether the same
  service is slow every time.
- Quoting raw `startTimeUnixNano` values instead of
  durations.
- Ignoring `traces_left_out` and the sampling ratio:
  the slowest traces are in the bundle, but not
  every slow request.
- Loading the files into a Tempo or Grafana to view
  them, or reading the customer's Tempo for more
  traces. Read the files; ask for a richer next
  bundle instead.
- Recommending `--include-traces` for a problem that
  is not a slowness, such as a crash with a clear
  traceback.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/collect/create)
