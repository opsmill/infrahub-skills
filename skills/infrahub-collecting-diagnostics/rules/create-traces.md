---
title: Offer traces for a slow instance, after the operator agrees
impact: HIGH
tags: create, flags, traces, slowness, token
---

## Offer traces for a slow instance, after the operator agrees

When the operator reports that Infrahub is slow, ask
whether to add the traces of the slow requests to the
bundle, and ask when the slowness happened. Add
`--include-traces` only after a yes. For any other
problem, do not offer traces.

Requires an `infrahub-collect` release that has
`--include-traces`. When `infrahub-collect create
--help` does not list it, say that this version cannot
collect traces and create the bundle without them.

### Why it matters

A trace records where the time of one request went:
each database query, each GraphQL resolver, each call
between services. It is the most direct evidence of a
slowness. The traces come from the operator's own
Tempo, so they also carry names from their deployment,
and the operator decides whether they leave the
deployment. The operator also reviews
`bundle/traces/` before sharing the bundle (see
[review-before-sharing.md](review-before-sharing.md)). That is why the option is asked, not
added.

Traces also need a window. A wrong window gives an
empty `traces/` folder, and the bundle cannot be
created again for a slowness that already ended.

### What to do

1. Ask whether to include traces. Then ask whether the
   slowness is still going on.
2. Choose the window from the answer:
   - Still going on: `--traces-since <duration>`, a
     window that ends now (default `2h`).
   - Ended: `--traces-start <time>` and
     `--traces-end <time>`, both in RFC 3339 (for
     example `2026-11-04T14:00:00Z`).
3. Say that only a share of requests has a trace, set
   by the trace sampling ratio of the deployment.
4. When the operator can reproduce the slowness, tell
   them that a user with the `super_admin` permission
   can raise the ratio for a limited time before they
   reproduce it, and must remove it after the bundle
   is created. The operator runs these calls, not the
   agent: the skill does not change Infrahub state
   (see [collection-read-only.md](collection-read-only.md)).

   ```bash
   # Before reproducing: record every new request for 30 minutes
   curl -X PUT "$INFRAHUB_ADDRESS/api/troubleshooting/trace-sample-ratio" \
     -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
     -d '{"ratio": 1.0, "duration_seconds": 1800}'

   # After the bundle is created: go back to the default ratio
   curl -X DELETE "$INFRAHUB_ADDRESS/api/troubleshooting/trace-sample-ratio" \
     -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN"
   ```

   The sampling ratio endpoint exists in Infrahub 1.12
   and later, and needs tracing turned on
   (`INFRAHUB_TRACE_ENABLE`).
5. Handle the tokens without seeing them. With
   `--include-traces`, `infrahub-collect` reads an API
   token with `super_admin` from
   `INFRAHUB_TRACES_API_TOKEN` to record the sampling
   ratio, and the token of a backend given with
   `--traces-tempo-url` from
   `INFRAHUB_TRACES_TEMPO_TOKEN`. In a terminal, it
   asks for them with a prompt that does not show what
   the operator types. When the agent runs the command
   through a tool, there is no prompt, and a variable
   the operator exports in another terminal does not
   reach the agent's process. Give the operator one of
   these choices:
   - Export the variables, then start the agent
     session from that same shell.
   - Save the token in a file that the agent never
     opens, and let the command read it:
     `INFRAHUB_TRACES_API_TOKEN="$(cat ~/.infrahub-admin-token)" infrahub-collect create ...`
   - Run the command themselves in their own terminal.

   Without the token, `create` still collects the
   traces but does not record the sampling ratio.
   Never ask for a token value in the conversation. A
   token pasted in the conversation is stored in the
   transcript.

### Compliant

```text
> The instance was slow. Do you want me to add the
> traces of the slow requests to the bundle? Is the
> slowness still going on, or when did it start and
> end?
>
> [operator: yes, 14:00 to 15:30 UTC today]
>
> Only a share of requests has a trace. Save your
> super_admin token in ~/.infrahub-admin-token; I will
> not open that file, and do not paste the token here.
>
> INFRAHUB_TRACES_API_TOKEN="$(cat ~/.infrahub-admin-token)" \
>   infrahub-collect create --include-traces \
>   --traces-start 2026-11-05T14:00:00Z --traces-end 2026-11-05T15:30:00Z
```

### Non-compliant

```text
> The instance is slow, so I added traces:
>
> infrahub-collect create --include-traces
>
> Paste your super_admin token here and I will set it.
```

### Common mistakes

- Adding `--include-traces` for a problem that is not
  slowness, such as a schema load failure or a crash.
- Adding the option without asking, or without a
  window that covers the slowness.
- Running the `PUT` or `DELETE` call on the sampling
  ratio from the agent, or leaving the raised ratio in
  place after the bundle is created.
- Asking the operator to paste a token in the
  conversation.

Reference: [Collect a diagnostic bundle](https://docs.infrahub.app/backup/collect/create)
