---
title: No customer data
impact: CRITICAL
tags: evidence, redaction, privacy
---

## No customer data

Impact: CRITICAL

A skill-friction report is filed against a public repository,
`opsmill/infrahub-skills`. Once it is filed it is indexed and cannot be
reliably retracted. This rule governs what the friction narrative may say
about the customer's schema, environment, and infrastructure before it is
handed off in step 6.

### Why it matters

[infrahub-reporting-issues](../../infrahub-reporting-issues/SKILL.md)'s
`environment-info-sanitization.md` scrubs product version and OS strings
for a bug report; that rule never sees the customer's data model. This
report's raw material is the customer's own schema, error text, and file
paths, gathered in step 1 from the current session. If this rule does not
scrub it before the handoff payload is built, nothing downstream will. An
earlier version of this skill tried to guarantee that with a Python
allowlist scrubber run over the whole session; it was replaced with this
rule because redaction only matters at the point the data actually leaves
the machine, which is the issue body, not a local file that already held
it.

### What is allowed

The body may contain, without redaction:

- The Infrahub skill name (for example `infrahub-managing-schemas`).
- Rule file paths inside this plugin (`skills/<skill>/rules/*.md`,
  `skills/<skill>/SKILL.md`).
- The plugin version.
- Generic descriptions of the modelling problem, stated abstractly enough
  that they would read the same regardless of which customer hit it.
- Public Infrahub vocabulary: schema keywords like
  `uniqueness_constraints`, `human_friendly_id`, `cardinality`,
  `on_delete`, generic kind names like `Device` or `Location`, and
  GraphQL terms.

### What must be redacted

| Pattern | Replace with |
| ------- | ------------ |
| Customer node kinds and namespaces (for example `AcmeDcimEdgeRouter`) | `<CustomerNode>` |
| Customer attribute and relationship names that encode business terms | `<attribute>` |
| Filesystem paths containing usernames or company names | `<path>` |
| Hostnames, internal URLs, IPv4 and IPv6 addresses | `<internal-host>`, `<internal-url>`, `<internal-ip>` |
| Company names anywhere in the body | `<org>` |
| Tokens, JWTs, connection strings | **abort and ask the user** |

The discriminating test: **if a reader could tell which company this came
from, redact it.**

### Abort-and-ask cases

If, after applying the table above, the body would still contain a
token, a JWT, or a connection string, stop. Do not hand off the draft.
Tell the user what was found and where, and ask them to remove it before
drafting continues. Partial redaction of a secret is not a fix; the
remaining characters are still enough to identify or replay it.

### Do not over-redact

Redaction removes identity, not information. A report reduced to
`<CustomerNode>` repeated with no surrounding description is
unactionable — the maintainer cannot tell what modelling problem it is
even describing. Paraphrase the structure of the problem generically
instead of deleting it:

- Instead of naming `AcmeDcimEdgeRouter`, write "a node with a uniqueness
  constraint spanning a relationship."
- Instead of pasting the customer's attribute name, write "an attribute
  encoding a business-specific identifier."
- Keep the schema mechanism intact — which constraint, which relationship
  shape, which validation step failed — only the customer's own names are
  the problem.

A draft that fails this half of the rule is as unfit to hand off as one
that leaks a hostname. It wastes the maintainer's time on the other side
of the same failure: nothing left to act on.

### Examples

**Non-compliant** (leaks company, node kind, path, host, IP):

```text
At Acme Energy, adding a uniqueness_constraint across the `site` and
`rack_position` relationship on AcmeDcimEdgeRouter kept failing. Working
from /Users/jsmith/acme-infra/schema.yml against
infrahub-db01.acme.internal (10.20.30.40), infrahubctl schema load
rejected the constraint twice.
```

**After sanitization** (compliant, still actionable):

```text
Adding a uniqueness_constraint spanning a relationship (two peer
attributes on a related node, not a single local attribute) on a
customer node kept failing schema load. Only the single-attribute case
is documented in this skill's rules.
```

**Over-redacted** (leaks nothing, but fails the rule anyway):

```text
Working with <CustomerNode> and <attribute> at <org> from <path> against
<internal-host> (<internal-ip>) did not work.
```

Nothing here tells a maintainer what modelling problem occurred. Every
specific has been deleted along with the customer's identity.

### Common mistakes

- Pasting an error message or stack trace verbatim; these carry file
  paths and kind names straight from the customer's schema.
- Redacting the node kind but leaving the company name in a sentence like
  "the router node at Acme kept rejecting the schema."
- Treating "the schema skill" as sufficient redaction of a rule file's
  path, when [evidence-cite-the-artifact.md](evidence-cite-the-artifact.md)
  requires the real path — that rule and this one govern different
  content in the same draft; the path is allowed and required, the
  customer's names around it are not.
- Redacting every noun to a placeholder rather than paraphrasing the
  modelling problem, producing a draft that leaks nothing and explains
  nothing.
- Assuming a customer name mentioned only once is safe to leave in; one
  mention is still a mention.

Reference:
[../../infrahub-reporting-issues/rules/environment-info-sanitization.md](../../infrahub-reporting-issues/rules/environment-info-sanitization.md)
for the sibling rule governing product-version and OS strings in a bug
report body; this rule governs the customer's schema detail in a friction
narrative instead.
