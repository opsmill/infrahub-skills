# Exercise Verification Methods

An exercise is presented only after its reference solution passed the
method below for its artifact type. Record the command and result in the
solution file's `## Verification` section. If no method is available in
the current environment, reshape the exercise into one that has a
method.

| Artifact | Method |
| --- | --- |
| Schema YAML | Offline validation: load the schema with the Infrahub SDK's in-memory validator, or `infrahubctl schema check <file>` when a client environment is configured. Either yields the verbatim load errors a server would raise. |
| Object YAML | Validate shape against the governing schema: confirm every referenced kind, attribute, and relationship exists in the schema files, then, when an instance and consent exist, `infrahubctl object load <file> --branch learning-<topic>`. Without an instance, the schema cross-check is the method. |
| GraphQL query | With an instance: execute the query read-only and record the result shape. Without one: resolve every queried field against the schema files. |
| Check or transform code | Run it locally: `infrahubctl check <name>` or `infrahubctl transform <name>` against sample data in the repo. |
| Conceptual (no artifact) | The answer must be derivable from a cited docs.infrahub.app page; the citation is the verification. Record the URL itself in `## Verification`. |

When the tooling itself is absent (no `infrahubctl`, no SDK), only
local-file and conceptual exercises are available; say so rather than
presenting an unverifiable exercise.

<!-- Verified against infrahub-sdk (infrahubctl) v1.23.1: `infrahubctl schema check`, `infrahubctl object load --branch`, `infrahubctl check <name>`, and `infrahubctl transform <name>` all match the installed CLI's --help output. -->
