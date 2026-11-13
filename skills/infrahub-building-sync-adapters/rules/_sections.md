# infrahub-sync Source Adapter — Rule Sections

1. **Probe (probe-)** — CRITICAL. Query the live API with
   the integration account before any spec, keep the
   responses as captures, and record the API's behavior
   in `api-behavior.yml`.

2. **Test (test-)** — CRITICAL. Unit-test fakes serve the
   captures and behave as the behavior file records,
   neither looser nor stricter than the real API.

3. **Retry (retry-)** — HIGH. The default retry and
   rate-limit policy of the adapter's HTTP client, and
   how the behavior file overrides it.

4. **Mapping (mapping-)** — CRITICAL. The sync
   configuration in the customer's repository: sync
   `identifiers` against the destination
   `human_friendly_id`, and the data check before the
   first run.

5. **Scope (scope-)** — HIGH. Which files an adapter
   change may touch, and how core problems become
   drafted issues.

6. **Gate (gate-)** — HIGH. The checks run before the
   push and listed in the pull request description.
