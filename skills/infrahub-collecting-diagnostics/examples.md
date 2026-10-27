# Examples — End-to-End Walk-throughs

Three realistic runs of the skill driving
`infrahub-collect` through the six workflow steps
from [SKILL.md](SKILL.md). These are reference
transcripts, not scripts to paste verbatim — the
exact flags come from [reference.md](reference.md).

## Example 1 — Git-sync failure on Docker Compose

### User opens

> "My proposed change is failing on schema load, repo
> isn't syncing. I'm on docker-compose. Can you grab
> what OpsMill needs to look at this?"

### Step 1: Capture the problem

Keywords noted: Docker Compose, git-sync/schema-load
failure, proposed change pipeline. Nothing here points
at performance or DB behavior, so no extra `create`
flags are needed yet.

### Step 2: Install & verify

```text
$ infrahub-collect version
infrahub-collect version 0.3.1
```

Already installed — skip the install steps.

### Step 3: Detect the environment

```text
$ infrahub-collect environment detect
Detected: Docker Compose, project "infrahub-prod"
```

Unambiguous — one Compose project, name contains
`infrahub`. No `--project` needed.

### Step 4: Create the bundle

```text
$ infrahub-collect create
Collecting bundle... done (3 warnings, 0 errors)
Bundle written to ./infrahub_bundles/2026-07-16T10-42-00/
```

The manifest recorded 3 warnings — the tool was still
able to collect logs for every service, so this is a
mostly-complete bundle, not a partial one.

### Step 5: Review before sharing (user-gate)

```text
Skill: Bundle's ready. infrahub-collect only masks
       values under keys named password/secret/token/
       key — it doesn't scrub log lines or query text.
       Check bundle_information.json for the 3 warnings
       it flagged, then skim bundle/logs/task-worker/
       and bundle/server/ for the CommitNotFoundError
       and anything sensitive (repo URLs, credentials
       under other key names). Let me know when it's
       OK to share.

User:  Looked through it, repo URL is internal-only
       and fine to share. Go ahead.
```

### Step 6: Share / hand off

```text
Skill: Send infrahub_bundles/2026-07-16T10-42-00/ to
       OpsMill support via your usual channel (Discord/
       Slack/email) along with a note that
       bundle_information.json shows 3 warnings during
       collection. Want to also file a public GitHub
       issue for this? If so, I'll switch to
       infrahub-reporting-issues next.

User:  No, just the support hand-off for now.
```

## Example 2 — Performance investigation on Kubernetes

### User opens

> "The UI has gotten really slow over the last day,
> and I saw a task-worker pod OOM-kill and restart.
> We're running on Kubernetes, namespace
> `infrahub-prod`."

### Step 1: Capture the problem

Keywords: Kubernetes, slow UI, OOM-kill, restarted
pod, namespace `infrahub-prod`. Performance/OOM
symptom → plan on `--benchmark` at step 4, and expect
a `*.previous.log` for the restarted pod.

### Step 2: Install & verify

```text
$ infrahub-collect version
command not found: infrahub-collect
$ curl https://infrahub.opsmill.io/ops/Linux/x86_64/infrahub-collect -o infrahub-collect
$ chmod +x infrahub-collect
$ sudo mv infrahub-collect /usr/local/bin/
$ infrahub-collect version
infrahub-collect version 0.3.1
```

### Step 3: Detect the environment

```text
$ infrahub-collect environment detect
No default namespace match (label app.kubernetes.io/name=infrahub
not found in current context's namespace).
$ infrahub-collect environment list
NAMESPACE          MATCH
infrahub-prod      label app.kubernetes.io/name=infrahub
```

The user already named the namespace, so pass it
explicitly rather than relying on default-context
detection.

### Step 4: Create the bundle

```text
$ infrahub-collect create --benchmark --k8s-namespace=infrahub-prod
Collecting bundle... running benchmark (host resource probe)... done
Bundle written to ./infrahub_bundles/2026-07-16T11-05-00/
```

`--benchmark` matches the reported OOM/slow-UI
symptom. If the benchmark image can't be pulled (e.g.
a restricted cluster registry), the tool skips that
step with a warning rather than failing the run —
still send whatever the bundle did collect.

### Step 5: Review before sharing (user-gate)

```text
Skill: Bundle's ready, including the benchmark results
       under bundle/metrics/. Since a task-worker pod
       restarted, check bundle/logs/task-worker/ for a
       *.previous.log — that's the pre-restart log
       OpsMill will want. Same masking caveat as
       always: skim for anything sensitive before I
       consider this done.

User:  Confirmed, previous.log is there and it's clean
       to share.
```

### Step 6: Share / hand off

```text
Skill: Send infrahub_bundles/2026-07-16T11-05-00/ to
       OpsMill support, and flag that it includes
       benchmark output plus a pre-restart task-worker
       log. Want me to also open a GitHub issue via
       infrahub-reporting-issues, or is the support
       hand-off enough for now?
```

## Example 3 — Slow database queries on Docker Compose

### User opens

> "GraphQL queries against a big dataset are taking
> way longer than they used to. Docker compose setup,
> single node."

### Step 1: Capture the problem

Keywords: slow GraphQL queries, DB-behavior symptom,
Docker Compose. This is exactly the case for
`--include-queries` at step 4 — flag it now, and note
the customer-data caution to raise before sharing.

### Step 2: Install & verify

```text
$ infrahub-collect version
infrahub-collect version 0.3.1
```

### Step 3: Detect the environment

```text
$ infrahub-collect environment detect
Detected: Docker Compose, project "infrahub"
```

### Step 4: Create the bundle

```text
$ infrahub-collect create --include-queries
Collecting bundle... done (0 warnings, 0 errors)
Bundle written to ./infrahub_bundles/2026-07-16T14-20-00/
```

`--include-queries` is off by default because it can
capture customer data in query text — it's justified
here because the symptom is specifically about query
behavior.

### Step 5: Review before sharing (user-gate)

```text
Skill: Bundle's ready. Because --include-queries was
       used, bundle/database/ now contains raw query
       text — this is NOT masked by key-name scrubbing
       and may contain customer data (record values,
       filter arguments). Please review bundle/database/
       and bundle/logs/ carefully — more so than usual —
       and confirm before this goes anywhere.

User:  Reviewed the query log, one query had a customer
       email in a filter argument. Can we strip that
       one query's log line before sending?

Skill: Sure — since infrahub-collect's masking is
       key-name only, we edit that manually: remove or
       redact the email in that specific line in
       bundle/database/<file>, then re-confirm before
       sharing.

User:  Done, redacted. OK to share now.
```

### Step 6: Share / hand off

```text
Skill: Send infrahub_bundles/2026-07-16T14-20-00/ to
       OpsMill support, noting it includes query logs
       (--include-queries) for the slow-query
       investigation, with one line manually redacted
       per your review. Also want a public GitHub issue
       via infrahub-reporting-issues, or just the
       support hand-off?

User:  Just the hand-off, thanks.
```
