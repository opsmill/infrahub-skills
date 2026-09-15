---
paths:
  - "graders/**/*.py"
---

# Grader Rules

Full reference: `dev/guides/adding-a-rule.md` §2 and §5,
`dev/guides/running-evals.md`

Graders are deterministic: no LLM grading, no network
calls. Inspect the parsed artifact and return a hard
pass/fail.

## Parse the answer; never substring-match it

`"x" in text` is the reflexive first draft, and the
commonest way a check goes wrong. It passes an answer
that merely mentions the trap and fails a correct answer
that words it differently. Parse the artifact instead:

| Artifact | Parse with |
| -------- | ---------- |
| Schema / object / menu YAML | `yaml.safe_load`, then walk the structure |
| Python (checks, generators, transforms) | `ast` |
| Shell commands | `shlex.split` — never split on `[;\|&]`, which fabricates segments inside quotes |
| Prose reports | locate the section, then rank evidence — see "Grading prose" below |

Three failure modes follow from matching raw text:

- **Comments and docstrings count as code.** Strip them
  before asserting, or a `# WRONG:` contrast block in
  the answer satisfies the check meant to fail it.
- **Only the first fence gets graded.** Extract every
  fenced block, and accept an answer whose entire output
  is fenced.
- **Adjacency is not structure.** A verb next to a path
  does not mean the command ran against that path.

## Grading prose: rank evidence, don't list phrasings

Some answers have nothing to parse: a
`verified_against` field, a `## Verification` section, a
justification sentence. Enumerating the phrasings a bad
answer might use is wrong in both directions at once,
and both are the same bug. Wording is unbounded.

Measured on a shipped check, one word apart:

```text
"the same form the sibling query uses"   -> 1.0, passed
"same form as the sibling query"         -> 0.8, FAILED
```

Three answers naming an introspected artifact and its
version failed too, on `mirrors the` and `elsewhere in
the repo`. The terse answer explaining nothing scored
1.0 and the thorough one scored 0, so the eval taught
the model to strip its reasoning out.

Ask what the check is really for, then test for that
directly, strongest evidence first:

1. An explicitly declared non-verification passes. The
   rule asks for exactly that honesty.
2. A named artifact or version passes, and may then
   discuss an analogy freely. Reasoning about evidence
   is not evidence by analogy.
3. Only then does a bare analogy fail.

Ordering it this way lets step 3 be broad without
punishing an answer resting on something real. Getting
it wrong compounds: a check that grades wording teaches
the next author to write what satisfies the regex rather
than what is correct.

## Check function shape

`graders/<skill>/lib.py` exposes a `CHECKS` registry
mapping assertion names to functions:

```python
def check_my_assertion(schema: dict, **_) -> tuple[bool, str]:
    """One-line summary of what this asserts."""
    if not_compliant:
        return False, "Specific failure message"
    return True, "Concise success message"
```

The failure message must name the assertion that
actually broke.

A rule cutting across multiple skills (rare) gets the
check duplicated in each `graders/<skill>/lib.py` rather
than hoisted to a shared module — the skills are
deliberately independently owned. Rules belonging to
`infrahub-common` grade from `graders/common/`.

`graders/auditing-repo/lib.py` is the one exception, and
this rule loads when you open it: its registry is
`_CHECKS`, private, keyed by colon-encoded
`<check>[:<arg>...]` names resolved through `_dispatch`,
and its check functions take `(findings, ...)` rather
than a parsed artifact. Read that file's own docstring
before adding to it; the shape above describes the other
fourteen.

## Verify both directions

The obvious compliant/violating pair catches neither
failure mode. Hand-craft **four** fixtures:

| Fixture | Expected |
| ------- | -------- |
| Compliant, written the way the rule shows | 1.0 |
| Compliant, written differently — other field order, a helper, a synonym | 1.0 |
| Violating, obviously | < 1.0 |
| Violating **near-miss** — satisfies the check's keyword while breaking the rule | < 1.0 |

The last of each pair finds the bugs:

- **False fail.** A correct answer phrased differently
  scores < 1.0.
- **Laundering.** A violating answer scores 1.0 because
  it mentions the right word, imports the right module,
  or names the right helper somewhere in the file. Ask
  what the smallest edit is that makes the violating
  fixture pass — if a comment or a bare string is
  enough, the check grades vocabulary, not substance.

## Don't hold a second copy of the prose

A grader that hard-codes a command tree, a kind list, or
a set of valid flags holds a second copy of the skill's
prose, and the two diverge the first time the prose
changes. Derive it from one place, or assert the shape
rather than the membership.

## Task grader scripts

`graders/<skill>/check_<task>.py` calls the shared
`run_checks` library and bundles the new assertion with
related baseline assertions (schema version, naming) so
the task catches regressions in neighbouring rules.

For `infrahub-auditing-repo` `yagni-*` rules, wire the
shared parameterized grader from `eval.yaml`
(`check_yagni_rule.py <rule> <severity> <ladder-step>`)
instead of adding a bespoke script. Write a dedicated
script only for file-attribution or carve-out checks the
parameterized grader cannot express.
